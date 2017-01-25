import _pickle as pickle
import numpy as np
import tensorflow as tf

from os.path import join
from datetime import datetime


CIFAR_DIR = 'datasets/cifar-batches'
MODEL_DIR = 'models/linear'
LOG_DIR = 'logs/{}'.format(str(datetime.now()).split('.')[0].replace(' ', '_'))


def load_cifar_batch(filename):
    with open(filename, 'rb') as f:
        datadict = pickle.load(f, encoding='latin1')
        X = datadict['data']
        Y = datadict['labels']
        X = X.reshape(10000, 3, 32, 32).transpose(0, 2, 3, 1).astype("float")
        Y = np.array(Y)
        return X, Y


def load_cifar(root=CIFAR_DIR):
    xs = []
    ys = []
    for b in range(1, 6):
        f = join(root, 'data_batch_%d' % (b, ))
        X, Y = load_cifar_batch(f)
        xs.append(X)
        ys.append(Y)
        Xtr = np.concatenate(xs)
        Ytr = np.concatenate(ys)
        del X, Y
        Xte, Yte = load_cifar_batch(join(root, 'test_batch'))
    return Xtr, Ytr, Xte, Yte


def get_cifar(num_training=49000, num_validation=1000, num_test=1000):
    # Load the raw CIFAR-10 data.
    X_train, y_train, X_test, y_test = load_cifar(CIFAR_DIR)

    # Make values range between 0 and 255.
    X_train /= 255.0
    X_test /= 255.0

    # Keep some training samples for validation.
    mask = range(num_training, num_training + num_validation)
    X_val = X_train[mask]
    y_val = y_train[mask]

    mask = range(num_training)
    X_train = X_train[mask]
    y_train = y_train[mask]

    mask = range(num_test)
    X_test = X_test[mask]
    y_test = y_test[mask]

    # Normalize the data: subtract the mean image.
    mean_image = np.mean(X_train, axis=0)
    X_train -= mean_image
    X_val -= mean_image
    X_test -= mean_image

    # Transpose so that channels come first.
    # X_train = X_train.transpose(0, 3, 1, 2).copy()
    # X_val = X_val.transpose(0, 3, 1, 2).copy()
    # X_test = X_test.transpose(0, 3, 1, 2).copy()

    # Package data into a dictionary.
    return {
      'X_train': X_train, 'y_train': y_train,
      'X_val': X_val, 'y_val': y_val,
      'X_test': X_test, 'y_test': y_test,
    }


def sample_batch(data, batch_size=256, split='train'):
    if split not in ['train', 'test', 'val']:
        raise ValueError

    X = data[f"X_{split}"]
    y = data[f"y_{split}"]
    indices = np.random.randint(0, X.shape[0], batch_size)

    return X[indices], y[indices]


def main():
    # Load data and print shapes.
    data = get_cifar()
    for k, v in data.items():
        print(f"{k:7}: {v.shape}")
    print()

    num_samples, width, height, channels = data['X_train'].shape
    num_classes = len(np.unique(data['y_train']))

    # Inputs to graph.
    X = tf.placeholder(tf.float32, shape=[None, width, height, channels])
    y_true = tf.placeholder(tf.int64, shape=[None])

    # Graph architecture.
    W = tf.Variable(
        tf.random_normal([width * height * channels, num_classes], stddev=0.01)
    )
    b = tf.Variable(tf.zeros([num_classes]))

    y_pred = tf.matmul(
        tf.reshape(X, [-1, width * height * channels]), W
    ) + b

    # Metrics operations.
    correct = tf.equal(tf.argmax(y_pred, axis=1), y_true)
    accuracy = tf.reduce_mean(tf.cast(correct, tf.float32))

    # Data and regularization loss operations.
    data_loss = tf.reduce_mean(
        tf.nn.sparse_softmax_cross_entropy_with_logits(y_pred, y_true)
    )

    reg = 1e-5
    reg_loss = reg * (
        tf.nn.l2_loss(W)
    )

    loss = data_loss + reg_loss

    # Declare and merge summary values.
    tf.summary.scalar('loss', loss)
    tf.summary.scalar('accuracy', accuracy)
    summarizer = tf.summary.merge_all()

    # Training operation; automatically updates all variables using SGD.
    learning_rate = 0.1
    global_step = tf.Variable(0, trainable=False)
    train_op = tf.train.GradientDescentOptimizer(
        learning_rate=learning_rate
    ).minimize(loss, global_step=global_step)

    # Operation to save and restore variables on the graph.
    saver = tf.train.Saver()

    # Create initializer for variables.
    init = tf.global_variables_initializer()

    epochs = 10
    batch_size = 256
    num_iterations = int(num_samples / batch_size) * epochs

    with tf.Session() as sess:
        # Run the initializer, then the rest.
        sess.run(init)

        # Create seaprate summary writers for training and validation data.
        train_writer = tf.summary.FileWriter(LOG_DIR + "/train", sess.graph)
        val_writer = tf.summary.FileWriter(LOG_DIR + "/val", sess.graph)

        # Run the training operation `num_iterations` times.
        for idx in range(num_iterations):
            # Sample a batch and build feed dict.
            X_batch, y_batch = sample_batch(data, batch_size=batch_size)
            feed = {X: X_batch, y_true: y_batch}

            # Run the training operation.
            _, summary, train_loss, train_acc = sess.run(
                [train_op, summarizer, loss, accuracy], feed_dict=feed
            )

            # Get and track metrics for validation and training sets.
            if idx % 100 == 0 or idx == (num_iterations - 1):
                train_writer.add_summary(summary, idx)

                feed = {X: data['X_val'], y_true: data['y_val']}
                summary, val_loss, val_acc = sess.run(
                    [summarizer, loss, accuracy],
                    feed_dict=feed
                )
                val_writer.add_summary(summary, idx)

                line = (
                    "iter = {}, train_loss = {:.2f}, train_acc = {:.2f}, "
                    "val_loss = {:.2f}, val_acc = {:.2f}"
                )
                print(line.format(
                    idx, train_loss, train_acc, val_loss, val_acc
                ))

                saver.save(sess, join(LOG_DIR, 'linear'), idx)

        # Saves the final variables of the graph to `MODEL_DIR`.
        save_path = saver.save(sess, MODEL_DIR)
        print()
        print(f"Saving result to {save_path}")


if __name__ == '__main__':
    main()
