import configparser
#import datetime  # Chronometer
import os
import tensorflow as tf
import numpy as np
import math
#Todo:- ask karan to have first character of class name as capital
from codes.dataset import dataset
from codes.model import RNNModel

class Bot:
    "Bot framework which integrates all the component"

    def __init__(self):
        #TODO:- Instead of using command line args we will go for config only
        # set the appropriate values from config compared to what was use as args
        # in original code

        self.text_data = None  # Dataset
        self.rnn_model = None  # Sequence to sequence model

        # Tensorflow utilities for convenience saving/logging
        self.writer = None
        self.saver = None
        self.model_dir = ''
        self.global_step = 0

        self.session = None

        # Filename and directories constants
        # Todo:- Move following to seperate config files
        self.root_dir
        self.MODEL_DIR_BASE = 'save/model'
        self.MODEL_NAME_BASE = 'model'
        self.MODEL_EXT = '.ckpt'
        self.CONFIG_FILENAME = 'params.ini'
        self.CONFIG_VERSION = '0.4'
        self.TEST_IN_NAME = 'data/test/samples.txt'
        self.TEST_OUT_SUFFIX = '_predictions.txt'
        self.SENTENCES_PREFIX = ['Q: ', 'A: ']

    def load_config(self):
        #Todo:- Load all the required values from the required configs
        self.keep_all = False
        self.ecpochs = 30
        self.learning_rate = 1e-4
        self.save_ckpt_at = 1000

    def main(self, **kwargs):
        #Todo:- sample call for Bot().main(rootdir="..", model="..", ....)

    def _save_session(self, session):
        self.saver.save(session, self._model_name())

    # Implementtion done, Testing remains
    def train_model(self, session):
        merged_summaries = tf.summary.merge_all()

        #Todo:- See if we can try making it possible to restore from previous run
        if self.global_step == 0:
            self.writer.add_graph(session.add_graph)

        print('Training begining (press Ctrl+C to save and exit)...')

        try:
            for epoch in range(self.epochs):
                print(
                      "\n----- Epoch {}/{} ; (lr={}) -----".format(
                        e+1,
                        self.epochs,
                        self.learning_rate
                        )
                      )
                batches = dataset.next_batch()

                for curr_batch in batches:
                    ops, feed_dict = self.rnn_model.step()
                    assert len(ops) == 2
                    _, loss, summary = session.run(ops + tuple([merged_summaries]), feed_dict)
                    self.writer.add_summary(summary, self.global_step)
                    self.global_step += 1

                    if self.globStep % 100 == 0:
                        perplexity = math.exp(float(loss)) if loss < 300 else float("inf")
                        print("----- Step %d -- Loss %.2f -- Perplexity %.2f" % (self.globStep, loss, perplexity))

                    #Save checkpoint
                    if self.global_step % self.save_ckpt_at == 0:
                        self._save_session(session)

        except (KeyboardInterrupt, SystemExit):
            print("Saving state and Exiting the program")

        self._save_session(session)

    def prediction_set(self, session):
        with open(os.path.join(self.root_dir, self.TEST_IN_NAME), 'r') as f:
            lines = f.readlines()

        model_list = self._get_model_list()
        if not modelList:
            print('Please Train the model first before predicting values')
            return

        for model in model_list:
            print('Restoring previous model from {}'.format(model))
            self.saver.restore(session, model)
            print('Testing...')

            save_name = model_name[:-len(self.MODEL_EXT)] + self.TEST_OUT_SUFFIX
            with open(save_name, 'w') as f:
                ignored_sen = 0
                for line in lines:
                    question = line[:-1]

                    answer = self.predict_single(question)
                    if not answer:
                        ignored_sen += 1
                        continue

                    prediction = '{x[0]}{0}\n{x[1]}{1}\n\n'.format(question, self.text_data.sequence2str(answer, clean=True), x=self.SENTENCES_PREFIX)
                    f.write(prediction)
                print('Prediction finished, {}/{} sentences ignored (too long)'.format(ignored_sen, len(lines)))

    def _get_model_list(self):
        model_list = [os.path.join(self.model_dir, f) for f in os.listdir(self.model_dir) if f.endswith(self.MODEL_EXT)]
        return sorted(model_list)

    # Implementation done, Testing remains
    def _model_name(self):
        model_name = os.path.join(self.model_dir, self.MODEL_NAME_BASE)
        if self.keep_all:
            model_name += '-' + str(self.global_step)
        return model_name + self.MODEL_EXT

    def predict_single(self, question, questionSeq=None):

        batch = self.text_data.sentence2enco(question)
        if not batch:
            return None
        #if questionSeq is not None:  # If the caller want to have the real input
        #    questionSeq.extend(batch.encoderSeqs)

        # Run the model
        ops, feedDict = self.model.step(batch)
        output = self.session.run(ops[0], feedDict)  # TODO: Summarize the output too (histogram, ...)
        answer = self.text_data.deco2sentence(output)

        return answer
