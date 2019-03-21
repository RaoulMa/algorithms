import numpy as np
import time

from sklearn.utils import check_random_state
from scipy.special import expit

def sigmoid_prime(z):
    p = expit(z)
    return p*(1 - p)

sigmoid = expit

random_state = check_random_state(None)

class LongShortTermMemoryNetwork:
    def __init__(self, n_blocks, learning_rate=1.0, n_epochs=20,
                 mu=0.5, output_activation='softmax',
                 random_state=None, verbose=0):
        self.n_blocks = n_blocks
        self.learning_rate = learning_rate
        self.n_epochs = n_epochs
        self.mu = mu
        self.output_activation = output_activation
        self.random_state = random_state
        self.verbose = verbose

        self.f = sigmoid
        self.g = sigmoid
        self.h = sigmoid

        self.f_prime = sigmoid_prime
        self.g_prime = sigmoid_prime
        self.h_prime = sigmoid_prime

    def init_parameters(self):
        sdev = 1.0 / np.sqrt(self.n_units_[0] + self.n_units_[1])

        # Weight matrices for weighted input to the cell
        dim = (self.n_units_[1], self.n_units_[0])
        self.Wh_ = self.random_state_.normal(0, sdev, size=dim)
        dim = (self.n_units_[1], self.n_units_[1])
        self.Whr_ = self.random_state_.normal(0, sdev, size=dim)
        # Bias vector for weighted input to the cell
        self.bh_ = np.zeros(self.n_units_[1])

        sdev = 1.0 / np.sqrt(self.n_units_[0] + self.n_units_[1] + 1)

        self.gates = ['input', 'forget', 'output']

        # Weight matrices for input, forget, and output gates
        self.Wgh_ = dict()
        self.Wghr_ = dict()
        # Weight vector (peephole weights) for input, forget and output gates
        self.wghs_ = dict()
        # Bias vector for input, forget and output gates
        self.bgh_ = dict()
        for g in self.gates:
            dim = (self.n_units_[1], self.n_units_[0])
            self.Wgh_[g] = self.random_state_.normal(0, sdev, size=dim)

            dim = (self.n_units_[1], self.n_units_[1])
            self.Wghr_[g] = self.random_state_.normal(0, sdev, size=dim)

            self.wghs_[g] = self.random_state_.normal(0, sdev,
                                                      size=self.n_units_[1])
            self.bgh_[g] = np.zeros(self.n_units_[1])

        # Weight matrix for output neurons
        sdev = 1.0 / np.sqrt(self.n_units_[1])
        dim = (self.n_units_[2], self.n_units_[1])
        self.Wo_ = self.random_state_.normal(0, sdev, size=dim)
        self.bo_ = self.random_state_.randn(self.n_units_[2])

        # Velocities (momentum-based gradient descent)
        self.VWh_ = np.zeros(self.Wh_.shape)
        self.VWhr_ = np.zeros(self.Whr_.shape)
        self.Vbh_ = np.zeros(self.bh_.shape)

        self.VWgh_ = dict()
        self.VWghr_ = dict()
        self.Vwghs_ = dict()
        self.Vbgh_ = dict()
        for g in self.gates:
            self.VWgh_[g] = np.zeros(self.Wgh_[g].shape)
            self.VWghr_[g] = np.zeros(self.Wghr_[g].shape)
            self.Vwghs_[g] = np.zeros(self.wghs_[g].shape)
            self.Vbgh_[g] = np.zeros(self.bgh_[g].shape)

        self.VWo_ = np.zeros(self.Wo_.shape)
        self.Vbo_ = np.zeros(self.bo_.shape)

    def fit(self, X, y):
        self.random_state_ = check_random_state(self.random_state)

        X = np.asarray(X)
        y = np.asarray(y)

        self.classes_ = np.unique(np.concatenate(y))
        classmap = {c: i for (i, c) in enumerate(self.classes_)}

        Y = []
        for yi in y:
            Yi = np.zeros((len(yi), len(self.classes_)))

            for t, yit in np.ndenumerate(yi):
                c = classmap[yit]
                Yi[t, c] = 1

            Y.append(Yi)
        Y = np.asarray(Y)

        self.n_units_ = [X[0].shape[1]] + [self.n_blocks] + [Y[0].shape[1]]

        self.init_parameters()
        self.online_gradient_descent(X, Y)


    def online_gradient_descent(self, X, Y):
        for epoch in range(self.n_epochs):
            now = time.time()

            s = self.random_state_.permutation(X.shape[0])
            Xs, Ys = X[s], Y[s]

            for Xi, Yi in zip(Xs, Ys):
                self.gradient_descent_step(Xi, Yi)

            if self.verbose > 0:
                now, last = time.time(), now
                print('Epoch {0} ({1:.01f}s).'.format(epoch + 1, now - last))


    def gradient_descent_step(self, Xi, Yi):
        T = len(Xi)

        states = []
        prev_h_a = np.zeros(self.n_units_[1])
        prev_h_s = np.zeros(self.n_units_[1])
        for t in range(T):
            x = Xi[t]

            state = self.forward_pass(x, prev_h_a, prev_h_s)

            prev_h_a = state['activation_output']
            prev_h_s = state['activation_cell']

            states.append(state)

        states.append({'activation_forget_gate': np.zeros(self.n_units_[1])})

        errors = self.backward_pass(Xi, Yi, states)
        self.update_parameters(states, errors, T)

    def forward_pass(self, x, prev_h_a, prev_h_s):
        state = dict()
        state['input_layer_activation'] = np.array(x)

        # LSTM layer
        for g in self.gates:
            z = self.Wgh_[g].dot(x) + self.Wghr_[g].dot(prev_h_a) + \
                self.wghs_[g] * prev_h_s + self.bgh_[g]

            state['weighted_input_{0}_gate'.format(g)] = z
            state['activation_{0}_gate'.format(g)] = self.f(z)

        z = self.Wh_.dot(x) + self.Whr_.dot(prev_h_a) + self.bh_
        state['weighted_input_cell'] = z

        aF = state['activation_forget_gate']
        aI = state['activation_input_gate']

        s = aF * prev_h_s + aI * self.g(z)
        state['activation_cell'] = s

        aO = state['activation_output_gate']
        state['activation_output'] = aO * self.h(s)

        # Output layer
        z = self.Wo_.dot(state['activation_output']) + self.bo_
        state['output_layer_weighted_input'] = z

        if self.output_activation == 'sigmoid':
            state['output_layer_activation'] = self.h(z)
        elif self.output_activation == 'softmax':
            Z = np.exp(z)
            state['output_layer_activation'] = Z / Z.sum()

        return state


    def backward_pass(self, Xi, Yi, states):
        T = len(Xi)

        errors = [dict() for _ in range(T + 1)]
        errors[T]['weighted_input_cell'] = np.zeros(self.n_units_[1])
        for g in self.gates:
            errors[T]['weighted_input_{0}_gate'.format(g)] = \
                np.zeros(self.n_units_[1])
        errors[T]['activation_cell'] = np.zeros(self.n_units_[1])

        # Error of the weighted input to the output layer
        for t in range(T):
            e = (states[t]['output_layer_activation'] - Yi[t]) / float(T)
            errors[t]['output_layer_weighted_input'] = e

        for t in reversed(range(T)):
            # Error of the output activation of the blocks
            e = self.Wo_.T.dot(errors[t]['output_layer_weighted_input'])
            e += self.Whr_.T.dot(errors[t + 1]['weighted_input_cell'])

            for g in self.gates:
                e += self.Wghr_[g].T.dot(errors[t + 1] \
                                             ['weighted_input_{0}_gate'.format(g)])

            errors[t]['activation_output'] = e

            # Error of the weighted input to the output gate
            e = self.f_prime(states[t]['weighted_input_output_gate']) * \
                self.h(states[t]['activation_cell']) * \
                errors[t]['activation_output']

            errors[t]['weighted_input_output_gate'] = e

            # Error of the cell activation of the blocks
            e = states[t]['activation_output_gate'] * \
                self.h_prime(states[t]['activation_cell']) * \
                errors[t]['activation_output']

            e += states[t + 1]['activation_forget_gate'] * \
                 errors[t + 1]['activation_cell']

            for g in self.gates:
                e += errors[t + 1]['weighted_input_{0}_gate'.format(g)] * \
                     self.wghs_[g]

            errors[t]['activation_cell'] = e

            # Error of the weighted input to the cell
            e = states[t]['activation_input_gate'] * \
                self.g_prime(states[t]['weighted_input_cell']) * \
                errors[t]['activation_cell']

            errors[t]['weighted_input_cell'] = e

            # Error of the weighted input to the forget gate
            if t > 0:
                e = self.f_prime(states[t]['weighted_input_forget_gate']) * \
                    states[t - 1]['activation_cell'] * \
                    errors[t]['activation_cell']
            else:
                e = np.zeros(self.n_units_[1])

            errors[t]['weighted_input_forget_gate'] = e

            # Error of the weighted input to the input gate
            e = self.f_prime(states[t]['weighted_input_input_gate']) * \
                self.g(states[t]['weighted_input_cell']) * \
                errors[t]['activation_cell']

            errors[t]['weighted_input_input_gate'] = e

        return errors


    def update_parameters(self, states, errors, T):
        # Parameters for weighted input to the cell
        partial_Wh = np.zeros(self.Wh_.shape)
        partial_Whr = np.zeros(self.Whr_.shape)
        partial_bh = np.zeros(self.bh_.shape)
        for t in range(T):
            delta = errors[t]['weighted_input_cell']

            partial_Wh += delta.reshape(-1, 1) \
                .dot(states[t]['input_layer_activation'].reshape(1, -1))

            if t > 0:
                partial_Whr += delta.reshape(-1, 1) \
                    .dot(states[t - 1]['activation_output'].reshape(1, -1))

            partial_bh += delta

        # Parameters for output layer
        partial_Wo = np.zeros(self.Wo_.shape)
        partial_bo = np.zeros(self.bo_.shape)
        for t in range(T):
            delta = errors[t]['output_layer_weighted_input']

            partial_Wo += delta.reshape(-1, 1) \
                .dot(states[t]['activation_output'].reshape(1, -1))

            partial_bo += delta

        # Parameters for weighted input to the gates
        partial_Wgh = dict()
        partial_Wghr = dict()
        partial_wghs = dict()
        partial_bgh = dict()
        for g in self.gates:
            partial_Wgh[g] = np.zeros(self.Wgh_[g].shape)
            partial_Wghr[g] = np.zeros(self.Wghr_[g].shape)
            partial_bgh[g] = np.zeros(self.bgh_[g].shape)
            partial_wghs[g] = np.zeros(self.wghs_[g].shape)

            for t in range(T):
                delta = errors[t]['weighted_input_{0}_gate'.format(g)]

                partial_Wgh[g] += delta.reshape(-1, 1). \
                    dot(states[t]['input_layer_activation'].reshape(1, -1))

                if t > 0:
                    partial_Wghr[g] += delta.reshape(-1, 1). \
                        dot(states[t - 1]['activation_output'].reshape(1, -1))

                    partial_wghs[g] += delta * states[t - 1]['activation_cell']

                partial_bgh[g] += delta

        # Update velocities
        lr = self.learning_rate

        self.VWh_ = self.mu * self.VWh_ - lr * partial_Wh
        self.Wh_ += self.VWh_

        self.VWhr_ = self.mu * self.VWhr_ - lr * partial_Whr
        self.Whr_ += self.VWhr_

        self.Vbh_ = self.mu * self.Vbh_ - lr * partial_bh
        self.bh_ += self.Vbh_

        for g in self.gates:
            self.VWgh_[g] = self.mu * self.VWgh_[g] - lr * partial_Wgh[g]
            self.Wgh_[g] += self.VWgh_[g]

            self.VWghr_[g] = self.mu * self.VWghr_[g] - lr * partial_Wghr[g]
            self.Wghr_[g] += self.VWghr_[g]

            self.Vwghs_[g] = self.mu * self.Vwghs_[g] - lr * partial_wghs[g]
            self.wghs_[g] += self.Vwghs_[g]

            self.Vbgh_[g] = self.mu * self.Vbgh_[g] - lr * partial_bgh[g]
            self.bgh_[g] += self.Vbgh_[g]

        self.VWo_ = self.mu * self.VWo_ - lr * partial_Wo
        self.Wo_ += self.VWo_

        self.Vbo_ = self.mu * self.Vbo_ - lr * partial_bo
        self.bo_ += self.Vbo_

        def predict_proba(self, X):
            Yp = []
            for Xi in X:
                Yip = np.zeros((Xi.shape[0], len(self.classes_)))

                prev_h_a = np.zeros(self.n_units_[1])
                prev_h_s = np.zeros(self.n_units_[1])
                for t in range(len(Xi)):
                    state = self.forward_pass(Xi[t], prev_h_a, prev_h_s)

                    prev_h_a = state['activation_output']
                    prev_h_s = state['activation_cell']

                    output = state['output_layer_activation']
                    Yip[t] = output / output.sum()

                Yp.append(Yip)

            Yp = np.asarray(Yp)

            return Yp

    def predict_proba(self, X):
        Yp = []
        for Xi in X:
            Yip = np.zeros((Xi.shape[0], len(self.classes_)))

            prev_h_a = np.zeros(self.n_units_[1])
            prev_h_s = np.zeros(self.n_units_[1])
            for t in range(len(Xi)):
                state = self.forward_pass(Xi[t], prev_h_a, prev_h_s)

                prev_h_a = state['activation_output']
                prev_h_s = state['activation_cell']

                output = state['output_layer_activation']
                Yip[t] = output / output.sum()

            Yp.append(Yip)

        Yp = np.asarray(Yp)

        return Yp

    def predict(self, X):
        ypred = []

        Yp = self.predict_proba(X)
        for Yip in Yp:
            Yiargmax = Yip.argmax(axis=1)
            ypred.append(self.classes_[Yiargmax])

        ypred = np.asarray(ypred)

        return ypred

    def score(self, X, y):
        acc = 0.0

        ypred = self.predict(X)
        for yipred, yi in zip(ypred, y):
            acc += float((yipred == yi).sum()) / len(yi)

        return acc / len(y)


def nback(n, k, length):
    """Random n-back targets given n, number of digits k and sequence length"""
    Xi = random_state.randint(k, size=length)
    yi = np.zeros(length, dtype=int)

    for t in range(n, length):
        yi[t] = (Xi[t - n] == Xi[t])

    return Xi, yi


def one_of_k(Xi_, k):
    Xi = np.zeros((len(Xi_), k))
    for t, Xit in np.ndenumerate(Xi_):
        Xi[t, Xit] = 1

    return Xi


def nback_dataset(n_sequences, mean_length, std_length, n, k):
    X, y = [], []

    for _ in range(n_sequences):
        length = random_state.normal(loc=mean_length, scale=std_length)
        length = int(max(n + 1, length))

        Xi_, yi = nback(n, k, length)
        Xi = one_of_k(Xi_, k)

        X.append(Xi)
        y.append(yi)

    return X, y


if __name__ == "__main__":

    # Input dimension
    k = 4
    # n-back
    n = 3

    n_sequences = 100
    mean_length = 20
    std_length = 5

    # Training
    Xtrain, ytrain = nback_dataset(n_sequences, mean_length, std_length, n, k)

    lstm = LongShortTermMemoryNetwork(64, learning_rate=2.0, n_epochs=70,
                                      mu=0.7, output_activation='softmax',
                                      random_state=None, verbose=1)

    lstm.fit(Xtrain, ytrain)

    # Evaluating
    Xtest, ytest = nback_dataset(5 * n_sequences, 5 * mean_length, 5 * std_length,
                                 n, k)

    print('\nTest score: {0:.3f}.'.format(lstm.score(Xtest, ytest)))

    acc_zeros = 0.0
    for yi in ytest:
        acc_zeros += float((yi == 0).sum()) / len(yi)
    acc_zeros /= len(ytest)
    print('Negative guess score: {0:.3f}.'.format(acc_zeros))

    # Example
    Xi_ = [3, 2, 1, 3, 2, 1, 3, 2, 2, 1, 2, 3, 1, 2, 0, 0, 2, 0]
    print('\nExample sequence: {0}.'.format(Xi_))
    yi = np.zeros(len(Xi_), dtype=int)
    for t in range(n, len(Xi_)):
        yi[t] = (Xi_[t - n] == Xi_[t])

    Xi = one_of_k(Xi_, k)

    yipred = lstm.predict([Xi])[0]
    print('Correct: \t{0}.'.format(yi))
    print('Predicted: \t{0}.'.format(yipred))
    print('Score: {0:.3f}.'.format(float((yi == yipred).sum()) / len(yi)))


