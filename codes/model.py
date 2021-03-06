import os
import tensorflow as tf
import configparser as cp
from dataset import batch

class initializer:
    def __init__(self, shape, scope=None, dtype=None):
        assert len(shape) == 2
        self.scope = scope
        with tf.variable_scope('weights_' + self.scope):
            self.W = tf.get_variable(
                'weights',
                shape,
                #initializer=tf.truncated_normal_initializer()
                dtype=dtype
            )
            self.b = tf.get_variable(
                'bias',
                shape[1],
                initializer=tf.constant_initializer(),
                dtype=dtype
            )
    def get_weight(self):
        return self.W, self.b

    def __call__(self, X):
        with tf.name_scope(self.scope):
            return tf.matmul(X, self.W) + self.b

#####################################################
# List of args (specified in Config.ini):           #
# learning rate 0.001                               #
# test True/False for testing/training              #
# maxLenDeco: maximum length of decoded output      #
# maxLenEnco: maximum length of input sequence      #
#####################################################

class RNNModel:
    def __init__(self, text_data, args):
        config = cp.ConfigParser()
        self.DirName='/'.join(os.getcwd().split('/')[:-1]);
        config.read(self.DirName+"/Database/Config.ini");
        self.test = config['General'].getboolean('test')
        self.textdata = text_data       #this will keep the text data object
        self.dtype = tf.float32
        self.encoder = None
        self.decoder = None
        self.dropout = config['General'].getfloat('dropout')
        self.decoder_target = None
        self.decoder_weight = None
        self.loss_fct = None
        self.opt_op = None
        self.outputs = None
        self.softmaxSamples = int(config.get('Model', 'softmaxSamples'))
        self.hiddenSize = int(config.get('Model', 'hiddenSize'))
        self.numLayers = int(config.get('Model', 'numLayers'))
        self.maxLenEnco = int(config.get('Dataset', 'maxLength'))
        self.maxLenDeco = self.maxLenEnco + 2 #Todo: will see if it needs to be in config
        self.embeddingSize = int(config.get('Model', 'embeddingSize'))
        self.learningRate = float(config.get('Model', 'learningRate'))
        self.attention = config['Bot'].getboolean('attention')
        self.device = config.get('General', 'device')
        self.build_network()           #this is done to compute the graph
        if args.test:
            self.test = True
        if args.attention:
            self.attention = True 
            
    def get_device(self):
        if 'cpu' in self.device:
            return self.device
        elif 'gpu' in self.device:
            return self.device
        elif self.device is None:
            return None
        else:
            print('Warning: Error detected in device name: {}, switching to default device'.format(self.device))
            return None

    # Define network configuration, loss function and optimizer #
    def build_network(self):
        outputProjection = None
        # Sampled softmax only makes sense if we sample less than vocabulary size.
        if 0 < self.softmaxSamples < self.textdata.vocab_size():
            outputProjection = initializer(
                (self.hiddenSize, self.textdata.vocab_size()),
                scope='softmax_projection',
                dtype=self.dtype
            )

            def sampledSoftmax(inputs, labels):
                labels = tf.reshape(labels, [-1, 1])  # Add one dimension (nb of true classes, here 1)

                # We need to compute the sampled_softmax_loss using 32bit floats to
                # avoid numerical instabilities.
                local_weight = tf.cast(tf.transpose(outputProjection.W), tf.float32)
                local_bias = tf.cast(outputProjection.b, tf.float32)
                local_inputs = tf.cast(inputs, tf.float32)

                return tf.cast(
                    tf.nn.sampled_softmax_loss(
                        local_weight,  # Should have shape [num_classes, dim]
                        local_bias,
                        local_inputs,
                        labels,
                        self.softmaxSamples,
                        self.textdata.vocab_size()),
                    self.dtype)

        # All the model params are initialized on CPU memory by default #
        # set this to self.device() if you want this also on GPU memory #
        with tf.device('/cpu:0'):
            enc_dec_cell = tf.contrib.rnn.BasicLSTMCell(self.hiddenSize,
                                                    state_is_tuple=True)
            if not self.test:
                enc_dec_cell = tf.contrib.rnn.DropoutWrapper(enc_dec_cell,input_keep_prob=1.0,output_keep_prob=self.dropout)
            
            enc_dec_cell = tf.contrib.rnn.MultiRNNCell([enc_dec_cell] * self.numLayers,state_is_tuple=True)
            self.encoder  = [tf.placeholder(tf.int32, [None, ]) for _ in range(self.maxLenEnco)]
            self.decoder  = [tf.placeholder(tf.int32,[None, ],name='inputs') for _ in range(self.maxLenDeco)]
            self.decoder_weights=[tf.placeholder(tf.float32,[None,],name='weights') for _ in range(self.maxLenDeco)];
            self.decoder_targets  = [tf.placeholder(tf.int32, [None, ],name='targets') for _ in range(self.maxLenDeco)]

            if self.attention:
                print("Running attention mechanism")
                decoder_outputs, states = tf.contrib.legacy_seq2seq.embedding_attention_seq2seq (
                        self.encoder,  # List<[batch=?, inputDim=1]>, list of size args.maxLength
                        self.decoder,  # For training, we force the correct output (feed_previous=False)
                        enc_dec_cell,
                        self.textdata.vocab_size(),
                        self.textdata.vocab_size(),  # Both encoder and decoder have the same number of class
                        embedding_size=self.embeddingSize,  # Dimension of each word
                        output_projection=outputProjection.getWeights() if outputProjection else None,
                        feed_previous=bool(self.test)
                    )
            else:
                print("Running rnn seq-2-seq")
                decoder_outputs, states = tf.contrib.legacy_seq2seq.embedding_rnn_seq2seq (
                        self.encoder,  # List<[batch=?, inputDim=1]>, list of size args.maxLength
                        self.decoder,  # For training, we force the correct output (feed_previous=False)
                        enc_dec_cell,
                        self.textdata.vocab_size(),
                        self.textdata.vocab_size(),  # Both encoder and decoder have the same number of class
                        embedding_size=self.embeddingSize,  # Dimension of each word
                        output_projection=outputProjection.getWeights() if outputProjection else None,
                        feed_previous=bool(self.test)
                    )

        if self.test:
            if not outputProjection:
                self.outputs = decoder_outputs
            else:
                self.outputs = [outputProjection(output) for output in decoder_outputs]
        
        else:
            # Define loss function, optimizer                               #
            # Customize device/gpu for gradient calculation in Config.ini   #
            with tf.device(self.get_device()):
                self.loss_fct = tf.contrib.legacy_seq2seq.sequence_loss(
                    decoder_outputs,
                    self.decoder_targets,
                    self.decoder_weights,
                    self.textdata.vocab_size(),
                    softmax_loss_function= sampledSoftmax if outputProjection else None
                )
                tf.summary.scalar('loss', self.loss_fct)

                opt = tf.train.AdamOptimizer(
                    learning_rate=self.learningRate,
                    beta1=0.9,
                    beta2=0.999,
                    epsilon=1e-08
                )
                self.opt_op = opt.minimize(self.loss_fct);

    # Defines how input is fed into network at each step #
    def step(self, batch):
        feed_dict = {}
        ops = None

        # Training Phase #
        if not self.test:
            feed_dict = {self.encoder[i]: batch.var_encoder[i]
                         for i in range(self.maxLenEnco)}
            feed_dict.update({self.decoder[i]: batch.var_decoder[i]
                              for i in range(self.maxLenDeco)})
            feed_dict.update({self.decoder_targets[i]: batch.var_target[i]
                              for i in range(self.maxLenDeco)})
            feed_dict.update({self.decoder_weights[i]: batch.var_weight[i]
                              for i in range(self.maxLenDeco)})
            ops = (self.opt_op, self.loss_fct)
        
        # Testing phase (equivalent to batchSize == 1) #
        else:
            feed_dict = {self.encoder[i]: batch.var_encoder[i]
                         for i in range(self.maxLenEnco)}
            feed_dict[self.decoder[0]]  = [self.textdata.var_token]
            ops = tuple([self.outputs])
        
        # Return one pass operator #
        return ops, feed_dict
