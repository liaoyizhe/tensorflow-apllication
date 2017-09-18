# -*- coding: utf-8 -*-
import tensorflow as tf
import numpy as np
from gen_image import text_to_array
from config import MAX_CAPTCHA, CHAR_SET_LEN, IMAGE_HEIGHT, IMAGE_WIDTH, MAX_ACCURACY
from gen_image import gen_require_captcha_image

# tf占位符 x输入值表示None个图片
x_input = tf.placeholder(tf.float32, [None, IMAGE_HEIGHT * IMAGE_WIDTH * 3])  # using the rgb image
# tf占位符 y输出值表示None个text
y_input = tf.placeholder(tf.float32, [None, CHAR_SET_LEN * MAX_CAPTCHA])
keep_prob = tf.placeholder(tf.float32)


def __weight_variable(shape, stddev=0.01):
    initial = tf.random_normal(shape, stddev=stddev)
    return tf.Variable(initial)


def __bias_variable(shape, stddev=0.1):
    initial = tf.random_normal(shape=shape, stddev=stddev)
    return tf.Variable(initial)


def __conv2d(x, w):
    # strides 代表移动的平长
    return tf.nn.conv2d(x, w, strides=[1, 1, 1, 1], padding='SAME')


def __max_pool_2x2(x):
    return tf.nn.max_pool(x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')

# 返回100张图片矩阵,
# 100个一个批次
def gen_next_batch(batch_size=100):
    batch_x = np.zeros([batch_size, IMAGE_HEIGHT * IMAGE_WIDTH * 3])
    batch_y = np.zeros([batch_size, MAX_CAPTCHA * CHAR_SET_LEN])

    for i in xrange(batch_size):

        text, image = gen_require_captcha_image()
        # 将三维图片张量变为一维数组,赋值到batch_x的i行上
        batch_x[i, :] = image.flatten() / 255.0
        # 将三维图片张量变为一维数组,复制到batch_y的i行上
        batch_y[i, :] = text_to_array(text)

    return batch_x, batch_y


def create_layer(x_input, keep_prob):
    x_image = tf.reshape(x_input, shape=[-1, IMAGE_WIDTH, IMAGE_HEIGHT, 3])

    # 定义第1个卷积层
    """
        重点解释卷积层构建
        x_image[图片数量,图片长度,图片宽度,图像通道](描述一个像素点,如果是灰度,那么只需要一个数值来描述它,就是单通道。如果一个像素点,有RGB三种颜色来描述它,就是三通道)] [100,160,60,3]
        w_c1[卷积核的高度，卷积核的宽度，图像通道数，卷积核个数] [5,5,3,32]
        卷积形式为SAME,并且卷积步数为1
        卷积后得出的share为[100, 160, 60, 32],再进行最大池化,减小输入大小[100, 80, 30, 32]
        经过三层卷积层神经后,得出[100, 20, 8, 64]
        再经过两层xx
        [100,1024]
        得出预测值[100, 8]
        参考文章 http://blog.csdn.net/mao_xiao_feng/article/details/53444333
                https://www.2cto.com/kf/201612/572952.html
    """
    w_c1 = __weight_variable([5, 5, 3, 32], stddev=0.1)  # 3x3 第一层32个卷积核 采用黑白色
    b_c1 = __bias_variable([32], stddev=0.1)
    h_c1 = tf.nn.relu(tf.nn.bias_add(__conv2d(x_image, w_c1), b_c1))  # 定义第一个卷积层
    h_pool1 = __max_pool_2x2(h_c1)  # 定义第一个池化层
    # h_pool1 = tf.nn.dropout(h_pool1, keep_prob)

    # 定义第2个卷积层
    w_c2 = __weight_variable([5, 5, 32, 64], stddev=0.1)
    b_c2 = __bias_variable([64], stddev=0.1)
    h_c2 = tf.nn.relu(tf.nn.bias_add(__conv2d(h_pool1, w_c2), b_c2))
    h_pool2 = __max_pool_2x2(h_c2)
    # h_pool2 = tf.nn.dropout(h_pool2, keep_prob)

    # 定义第3个卷积层
    w_c3 = __weight_variable([5, 5, 64, 64], stddev=0.1)
    b_c3 = __bias_variable([64], stddev=0.1)
    h_c3 = tf.nn.relu(tf.nn.bias_add(__conv2d(h_pool2, w_c3), b_c3))
    h_pool3 = __max_pool_2x2(h_c3)
    # h_pool3 = tf.nn.dropout(h_pool3, keep_prob)

    # 3层池化之后 width 144 / 8 = 18
    # height 64 / 8 = 8
    # 全链接层1
    w_fc1 = __weight_variable([20 * 8 * 64, 1024], stddev=0.1)
    b_fc1 = __bias_variable([1024])
    h_pool3_flat = tf.reshape(h_pool3, [-1, w_fc1.get_shape().as_list()[0]])
    h_fc1 = tf.nn.relu(tf.add(tf.matmul(h_pool3_flat, w_fc1), b_fc1))
    # drop out 内容0
    h_fc1_dropout = tf.nn.dropout(h_fc1, keep_prob)
    # 全链接层2
    w_output = __weight_variable([1024, MAX_CAPTCHA * CHAR_SET_LEN], stddev=0.1)
    b_output = __bias_variable([MAX_CAPTCHA * CHAR_SET_LEN])
    y_output = tf.add(tf.matmul(h_fc1_dropout, w_output), b_output)

    return y_output

# 计算损失
def create_loss(layer, y_input):
    # 交叉熵,并求平均值
    loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(labels=y_input, logits=layer))
    return loss


def create_accuracy(output, y_input):
    predict = tf.reshape(output, [-1, MAX_CAPTCHA, CHAR_SET_LEN])
    max_idx_p = tf.argmax(predict, 2)
    max_idx_l = tf.argmax(tf.reshape(y_input, [-1, MAX_CAPTCHA, CHAR_SET_LEN]), 2)
    correct_pred = tf.equal(max_idx_p, max_idx_l)
    accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))
    return accuracy

"""
    开始训练
"""
def train():
    # create the layer and loss
    layer_output = create_layer(x_input, keep_prob)
    loss = create_loss(layer_output, y_input)
    accuracy = create_accuracy(layer_output, y_input)
    train_step = tf.train.AdamOptimizer(learning_rate=0.001).minimize(loss)
    # save model
    saver = tf.train.Saver()

    with tf.Session() as sess:
        tf.global_variables_initializer().run()
        acc = 0.0
        i = 0
        while True:
            i = i + 1
            # 获取100个数据
            batch_x, batch_y = gen_next_batch(64)

            _, _loss = sess.run([train_step, loss],
                                feed_dict={x_input: batch_x, y_input: batch_y, keep_prob: 0.75})
            # print(i, _loss)
            # 每100 step计算一次准确率
            if i % 50 == 0:
                batch_x_test, batch_y_test = gen_next_batch(100)
                acc = sess.run(accuracy, feed_dict={x_input: batch_x_test, y_input: batch_y_test, keep_prob: 1.})
                print('step is %s' % i, 'and accy is %s' % acc)
                # 如果准确率大于50%,保存模型,完成训练
                if acc > MAX_ACCURACY:
                    print('current acc > %s  ,stop now' % MAX_ACCURACY)
                    saver.save(sess, "break.model", global_step=i)
                    break


if __name__ == '__main__':
    train()
