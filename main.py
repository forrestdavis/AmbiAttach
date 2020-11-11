'''
Code for training and evaluating a neural language model.
LM can output incremental complexity measures and be made adaptive.
'''

from __future__ import print_function
import argparse
import time
import math
import sys
import warnings
import torch
import torch.nn as nn
import data
import model

try:
    from progress.bar import Bar
    PROGRESS = True
except ModuleNotFoundError:
    PROGRESS = False

# suppress SourceChangeWarnings
warnings.filterwarnings("ignore")

sys.stderr.write('Libraries loaded\n')

# Parallelization notes:
#   Does not currently operate across multiple nodes
#   Single GPU is better for default: tied,emsize:200,nhid:200,nlayers:2,dropout:0.2
#
#   Multiple GPUs are better for tied,emsize:1500,nhid:1500,nlayers:2,dropout:0.65
#      4 GPUs train on wikitext-2 in 1/2 - 2/3 the time of 1 GPU

parser = argparse.ArgumentParser(description='PyTorch RNN/LSTM Language Model')

# Model parameters
parser.add_argument('--model', type=str, default='LSTM',
                    choices=['RNN_TANH', 'RNN_RELU', 'LSTM', 'GRU'],
                    help='type of recurrent net')
parser.add_argument('--emsize', type=int, default=200,
                    help='size of word embeddings')
parser.add_argument('--nhid', type=int, default=200,
                    help='number of hidden units per layer')
parser.add_argument('--nlayers', type=int, default=2,
                    help='number of layers')
parser.add_argument('--lr', type=float, default=20,
                    help='initial learning rate')
parser.add_argument('--clip', type=float, default=0.25,
                    help='gradient clipping')
parser.add_argument('--epochs', type=int, default=40,
                    help='upper epoch limit')
parser.add_argument('--batch_size', type=int, default=20, metavar='N',
                    help='batch size')
parser.add_argument('--bptt', type=int, default=35,
                    help='sequence length')
parser.add_argument('--dropout', type=float, default=0.2,
                    help='dropout applied to layers (0 = no dropout)')
parser.add_argument('--tied', action='store_true',
                    help='tie the word embedding and softmax weights')
parser.add_argument('--seed', type=int, default=1111,
                    help='random seed')
parser.add_argument('--cuda', action='store_true',
                    help='use CUDA')
parser.add_argument('--init', type=float, default=None,
                    help='-1 to randomly Initialize. Otherwise, all parameter weights set to value')

# Data parameters
parser.add_argument('--model_file', type=str, default='model.pt',
                    help='path to save the final model')
parser.add_argument('--adapted_model', type=str, default='adaptedmodel.pt',
                    help='new path to save the final adapted model')
parser.add_argument('--data_dir', type=str, default='./data/wikitext-2',
                    help='location of the corpus data')
parser.add_argument('--vocab_file', type=str, default='vocab.txt',
                    help='path to save the vocab file')
parser.add_argument('--embedding_file', type=str, default=None,
                    help='path to pre-trained embeddings')
parser.add_argument('--trainfname', type=str, default='train.txt',
                    help='name of the training file')
parser.add_argument('--validfname', type=str, default='valid.txt',
                    help='name of the validation file')
parser.add_argument('--testfname', type=str, default='test.txt',
                    help='name of the test file')
parser.add_argument('--collapse_nums_flag', action='store_true',
                    help='collapse number tokens into a unified <num> token')

# Runtime parameters
parser.add_argument('--test', action='store_true',
                    help='test a trained LM')
parser.add_argument('--load_checkpoint', action='store_true',
                    help='continue training a pre-trained LM')
parser.add_argument('--single', action='store_true',
                    help='use only a single GPU (even if more are available)')
parser.add_argument('--multisentence_test', action='store_true',
                    help='treat multiple sentences as a single stream at test time')

parser.add_argument('--adapt', action='store_true',
                    help='adapt model weights during evaluation')
parser.add_argument('--interact', action='store_true',
                    help='run a trained network interactively')
parser.add_argument('--view_layer', type=int, default=-1,
                    help='which layer should output cell states')
parser.add_argument('--view_hidden', action='store_true',
                    help='output the hidden state rather than the cell state')

parser.add_argument('--words', action='store_true',
                    help='evaluate word-level complexities (instead of sentence-level loss)')
parser.add_argument('--log_interval', type=int, default=200, metavar='N',
                    help='report interval')

parser.add_argument('--lowercase', action='store_true',
                    help='force all input to be lowercase')
parser.add_argument('--nopp', action='store_true',
                    help='suppress evaluation perplexity output')
parser.add_argument('--nocheader', action='store_true',
                    help='suppress complexity header')
parser.add_argument('--csep', type=str, default=' ',
                    help='change the separator in the complexity output')

parser.add_argument('--guess', action='store_true',
                    help='display best guesses at each time step')
parser.add_argument('--guessn', type=int, default=1,
                    help='output top n guesses')
parser.add_argument('--guessscores', action='store_true',
                    help='display guess scores along with guesses')
parser.add_argument('--guessratios', action='store_true',
                    help='display guess ratios normalized by best guess')
parser.add_argument('--guessprobs', action='store_true',
                    help='display guess probs along with guesses')
parser.add_argument('--complexn', type=int, default=0,
                    help='compute complexity only over top n guesses (0 = all guesses)')

# Misc parameters not in README
parser.add_argument('--softcliptopk', action="store_true",
                    help='soften non top-k options instead of removing them')

args = parser.parse_args()

if args.interact:
    # If in interactive mode, force complexity output
    args.words = True
    args.test = True
    # Don't try to process multiple sentences in parallel interactively
    args.single = True

if args.adapt:
    # If adapting, we must be in test mode
    args.test = True

# Set the random seed manually for reproducibility.
torch.manual_seed(args.seed)
if torch.cuda.is_available():
    if not args.cuda:
        print("WARNING: You have a CUDA device, so you should probably run with --cuda")
    else:
        torch.cuda.manual_seed(args.seed)
        if torch.cuda.device_count() == 1:
            args.single = True

device = torch.device("cuda" if args.cuda else "cpu")


###############################################################################
# Load data
###############################################################################

def batchify(data, bsz):
    ''' Starting from sequential data, batchify arranges the dataset into columns.
    For instance, with the alphabet as the sequence and batch size 4, we'd get
    a g m s
    b h n t
    c i o u
    d j p v
    e k q w
    f l r x
    These columns are treated as independent by the model, which means that the
    dependence of e. g. 'g' on 'f' can not be learned, but allows more efficient
    batch processing.
    '''
    # Work out how cleanly we can divide the dataset into bsz parts.
    nbatch = data.size(0) // bsz
    # Trim off any extra elements that wouldn't cleanly fit (remainders).
    data = data.narrow(0, 0, nbatch * bsz)
    # Evenly divide the data across the bsz batches.
    data = data.view(bsz, -1).t().contiguous()
    # Turning the data over to CUDA at this point may lead to more OOM errors
    return data.to(device)

try:
    with open(args.vocab_file, 'r') as f:
        # We're using a pre-existing vocab file, so we shouldn't overwrite it
        args.predefined_vocab_flag = True
except FileNotFoundError:
    # We should create a new vocab file
    args.predefined_vocab_flag = False

corpus = data.SentenceCorpus(args.data_dir, args.vocab_file, args.test, args.interact,
                             checkpoint_flag=args.load_checkpoint,
                             predefined_vocab_flag=args.predefined_vocab_flag,
                             collapse_nums_flag=args.collapse_nums_flag,
                             multisentence_test_flag=args.multisentence_test,
                             lower_flag=args.lowercase,
                             trainfname=args.trainfname,
                             validfname=args.validfname,
                             testfname=args.testfname)

if not args.interact:
    if args.test:
        if args.multisentence_test:
            test_data = [corpus.test]
        else:
            test_sents, test_data = corpus.test
    else:
        train_data = batchify(corpus.train, args.batch_size)
        val_data = batchify(corpus.valid, args.batch_size)

###############################################################################
# Build/load the model
###############################################################################

if not args.test and not args.interact:
    if args.load_checkpoint:
        # Load the best saved model.
        print('  Continuing training from previous checkpoint')
        with open(args.model_file, 'rb') as f:
            if args.cuda:
                model = torch.load(f).to(device)
            else:
                model = torch.load(f, map_location='cpu')
    else:
        ntokens = len(corpus.dictionary)
        model = model.RNNModel(args.model, ntokens, args.emsize, args.nhid,
                               args.nlayers, embedding_file=args.embedding_file,
                               dropout=args.dropout, tie_weights=args.tied).to(device)

    # after load the rnn params are not a continuous chunk of memory
    # this makes them a continuous chunk, and will speed up forward pass
    if isinstance(model, torch.nn.DataParallel):
        # if multi-gpu, access real model for training
        model = model.module
    elif args.cuda:
        if (not args.single) and (torch.cuda.device_count() > 1):
            # If applicable, use multi-gpu for training
            # Scatters minibatches (in dim=1) across available GPUs
            model = nn.DataParallel(model, dim=1)
    model.rnn.flatten_parameters()

criterion = nn.CrossEntropyLoss()

###############################################################################
# Complexity measures
###############################################################################

def get_entropy(state):
    ''' Computes entropy of input vector '''
    # state should be a vector scoring possible classes
    # returns a scalar entropy over state
    if args.complexn == 0:
        beam = state
    else:
        # duplicate state but with all losing guesses set to 0
        beamk, beamix = torch.topk(state, args.complexn, 0)
        if args.softcliptopk:
            beam = torch.FloatTensor(state.size()).to(device).fill_(0).scatter(0, beamix, beamk)
        else:
            beam = torch.FloatTensor(state.size()).to(device).fill_(float("-inf")).scatter(0, beamix, beamk)

    probs = nn.functional.softmax(beam, dim=0)
    # log_softmax is numerically more stable than two separate operations
    logprobs = nn.functional.log_softmax(beam, dim=0)
    prod = probs.data * logprobs.data
    # sum but ignore nans
    return torch.Tensor([-1 * torch.sum(prod[prod == prod])]).to(device)

def get_surps(state):
    ''' Computes surprisal for each element in given vector '''
    # state should be a vector scoring possible classes
    # returns a vector containing the surprisal of each class in state
    if args.complexn == 0:
        beam = state
    else:
        # duplicate state but with all losing guesses set to 0
        beamk, beamix = torch.topk(state, args.complexn, 0)
        if args.softcliptopk:
            beam = torch.FloatTensor(state.size()).to(device).fill_(0).scatter(0, beamix, beamk)
        else:
            beam = torch.FloatTensor(state.size()).to(device).fill_(float("-inf")).scatter(0, beamix, beamk)

    logprobs = nn.functional.log_softmax(beam, dim=0)
    return -1 * logprobs

def get_guesses(state, scores=False):
    ''' Returns top-k guesses or guess indices of given vector '''
    # state should be a vector scoring possible classes
    guessvals, guessixes = torch.topk(state, args.guessn, 0)
    # guessvals are the scores of each input cell
    # guessixes are the indices of the max cells
    if scores:
        return guessvals
    else:
        return guessixes

def get_guessscores(state):
    ''' Wrapper that returns top-k guesses of given vector '''
    return get_guesses(state, True)

def get_complexity(state, obs, sentid):
    ''' Generates complexity output for given state, observation, and sentid '''
    Hs = torch.log2(torch.exp(torch.squeeze(apply(get_entropy, state))))
    surps = torch.log2(torch.exp(apply(get_surps, state)))

    if args.guess:
        guesses = apply(get_guesses, state)
        guessscores = apply(get_guessscores, state)

    for corpuspos, targ in enumerate(obs):
        word = corpus.dictionary.idx2word[int(targ)]
        if word == '<eos>':
            # don't output the complexity of EOS
            continue
        surp = surps[corpuspos][int(targ)]
        if args.guess:
            outputguesses = []
            for guess_ix in range(args.guessn):
                outputguesses.append(corpus.dictionary.idx2word[int(guesses[corpuspos][guess_ix])])
                if args.guessscores:
                    # output raw scores
                    outputguesses.append("{:.3f}".format(float(guessscores[corpuspos][guess_ix])))
                elif args.guessratios:
                    # output scores (ratio of score(x)/score(best guess)
                    outputguesses.append("{:.3f}".format(
                        float(guessscores[corpuspos][guess_ix])/float(guessscores[corpuspos][0])))
                elif args.guessprobs:
                    # output probabilities
                    # Currently normalizes probs over N-best list;
                    # ideally it'd normalize to probs before getting the N-best
                    outputguesses.append("{:.3f}".format(
                        math.exp(float(nn.functional.log_softmax(guessscores[corpuspos], dim=0)[guess_ix]))))
            outputguesses = args.csep.join(outputguesses)
            print(args.csep.join([str(word), str(sentid), str(corpuspos), str(len(word)),
                                  str(float(surp)), str(float(Hs[corpuspos])),
                                  str(max(0, float(Hs[max(corpuspos-1, 0)])-float(Hs[corpuspos]))),
                                  str(outputguesses)]))
        else:
            print(args.csep.join([str(word), str(sentid), str(corpuspos), str(len(word)),
                                  str(float(surp)), str(float(Hs[corpuspos])),
                                  str(max(0, float(Hs[max(corpuspos-1, 0)])-float(Hs[corpuspos])))]))

def apply(func, apply_dimension):
    ''' Applies a function along a given dimension '''
    output_list = [func(m) for m in torch.unbind(apply_dimension, dim=0)]
    return torch.stack(output_list, dim=0)

###############################################################################
# Training code
###############################################################################

def repackage_hidden(in_state):
    """ Wraps hidden states in new Tensors, to detach them from their history. """
    if isinstance(in_state, torch.Tensor):
        return in_state.detach()
    else:
        return tuple(repackage_hidden(value) for value in in_state)

def get_batch(source, i):
    """ get_batch subdivides the source data into chunks of length args.bptt.
    If source is equal to the example output of the batchify function, with
    a bptt-limit of 2, we'd get the following two Variables for i = 0:
    a g m s      b h n t
    b h n t      c i o u
    Note that despite the name of the function, the subdivison of data is not
    done along the batch dimension (i.e. dimension 1), since that was handled
    by the batchify function. The chunks are along dimension 0, corresponding
    to the seq_len dimension in the LSTM. """
    seq_len = min(args.bptt, len(source) - 1 - i)
    data = source[i:i+seq_len]
    target = source[i+1:i+1+seq_len].view(-1)
    return data, target

def test_get_batch(source):
    """ Creates an input/target pair for evaluation """
    seq_len = len(source) - 1
    data = source[:seq_len]
    target = source[1:1+seq_len].view(-1)
    return data, target

def test_evaluate(test_sentences, data_source):
    """ Evaluate at test time (with adaptation, complexity output) """
    # Turn on evaluation mode which disables dropout.
    if args.adapt:
        # Must disable cuDNN in order to backprop during eval
        torch.backends.cudnn.enabled = False
    model.eval()
    total_loss = 0.
    ntokens = len(corpus.dictionary)
    nwords = 0
    if args.complexn > ntokens or args.complexn <= 0:
        args.complexn = ntokens
        if args.guessn > ntokens:
            args.guessn = ntokens
        sys.stderr.write('Using beamsize: '+str(ntokens)+'\n')
    else:
        sys.stderr.write('Using beamsize: '+str(args.complexn)+'\n')

    if args.words:
        if not args.nocheader:
            if args.complexn == ntokens:
                print('word{0}sentid{0}sentpos{0}wlen{0}surp{0}entropy{0}entred'.format(args.csep), end='')
            else:
                print('word{0}sentid{0}sentpos{0}wlen{0}surp{1}{0}entropy{1}{0}entred{1}'.format(args.csep, args.complexn), end='')
            if args.guess:
                for i in range(args.guessn):
                    print('{0}guess'.format(args.csep)+str(i), end='')
                    if args.guessscores:
                        print('{0}gscore'.format(args.csep)+str(i), end='')
                    elif args.guessprobs:
                        print('{0}gprob'.format(args.csep)+str(i), end='')
                    elif args.guessratios:
                        print('{0}gratio'.format(args.csep)+str(i), end='')
            sys.stdout.write('\n')
    if PROGRESS:
        bar = Bar('Processing', max=len(data_source))
    for i in range(len(data_source)):
        sent_ids = data_source[i].to(device)
        # We predict all words but the first, so determine loss for those
        if test_sentences:
            sent = test_sentences[i]
        hidden = model.init_hidden(1) # number of parallel sentences being processed
        data, targets = test_get_batch(sent_ids)
        if args.view_layer >= 0:
            for word_index in range(data.size(0)):
                # Starting each batch, detach the hidden state
                hidden = repackage_hidden(hidden)
                model.zero_grad()

                word_input = data[word_index].unsqueeze(0).unsqueeze(1)
                target = targets[word_index].unsqueeze(0)
                output, hidden = model(word_input, hidden)
                output_flat = output.view(-1, ntokens)
                loss = criterion(output_flat, target)
                total_loss += loss.item()
                targ_word = corpus.dictionary.idx2word[int(target.data)]
                nwords += 1
                if targ_word != '<eos>':
                    # don't output <eos> markers to align with input
                    # output raw activations
                    if args.view_hidden:
                        # output hidden state
                        print(*list(hidden[0][args.view_layer].view(1, -1).data.cpu().numpy().flatten()), sep=' ')
                    else:
                        # output cell state
                        print(*list(hidden[1][args.view_layer].view(1, -1).data.cpu().numpy().flatten()), sep=' ')
        else:
            data = data.unsqueeze(1) # only needed when a single sentence is being processed
            output, hidden = model(data, hidden)
            try:
                output_flat = output.view(-1, ntokens)
            except RuntimeError:
                print("Vocabulary Error! Most likely there weren't unks in training and unks are now needed for testing")
                raise
            loss = criterion(output_flat, targets)
            total_loss += loss.item()
            if args.words:
                # output word-level complexity metrics
                get_complexity(output_flat, targets, i)
            else:
                # output sentence-level loss
                if test_sentences:
                    print(str(sent)+":"+str(loss.item()))
                else:
                    print(str(loss.item()))

            if args.adapt:
                loss.backward()

                # `clip_grad_norm` helps prevent the exploding gradient problem in RNNs / LSTMs.
                torch.nn.utils.clip_grad_norm(model.parameters(), args.clip)
                for param in model.parameters():
                    if param.grad is not None:
                    # only update trainable parameters
                        param.data.add_(-lr, param.grad.data)

        hidden = repackage_hidden(hidden)

        if PROGRESS:
            bar.next()
    if PROGRESS:
        bar.finish()
    if args.view_layer >= 0:
        return total_loss / nwords
    else:
        return total_loss / len(data_source)

def evaluate(data_source):
    """ Evaluate for validation (no adaptation, no complexity output) """
    # Turn on evaluation mode which disables dropout.
    model.eval()
    total_loss = 0.
    ntokens = len(corpus.dictionary)
    hidden = model.init_hidden(args.batch_size)
    with torch.no_grad():
        for i in range(0, data_source.size(0) - 1, args.bptt):
            data, targets = get_batch(data_source, i)
            output, hidden = model(data, hidden)
            output_flat = output.view(-1, ntokens)
            total_loss += len(data) * criterion(output_flat, targets).item()
            hidden = repackage_hidden(hidden)
    return total_loss / len(data_source)

def train():
    """ Train language model """
    # Turn on training mode which enables dropout.
    model.train()
    total_loss = 0.
    start_time = time.time()
    ntokens = len(corpus.dictionary)
    hidden = model.init_hidden(args.batch_size)
    for batch, i in enumerate(range(0, train_data.size(0) - 1, args.bptt)):
        data, targets = get_batch(train_data, i)
        # Starting each batch, we detach the hidden state from how it was previously produced.
        # If we didn't, the model would try backpropagating all the way to start of the dataset.
        hidden = repackage_hidden(hidden)
        model.zero_grad()
        output, hidden = model(data, hidden)
        loss = criterion(output.view(-1, ntokens), targets)
        loss.backward()

        # `clip_grad_norm` helps prevent the exploding gradient problem in RNNs / LSTMs.
        torch.nn.utils.clip_grad_norm(model.parameters(), args.clip)
        for param in model.parameters():
            if param.grad is not None:
                # only update trainable parameters
                param.data.add_(-lr, param.grad.data)

        total_loss += loss.item()

        if batch % args.log_interval == 0 and batch > 0:
            cur_loss = total_loss / args.log_interval
            elapsed = time.time() - start_time
            print('| epoch {:3d} | {:5d}/{:5d} batches | lr {:02.2f} | ms/batch {:5.2f} | '
                  'loss {:5.2f} | ppl {:8.2f}'.format(
                      epoch, batch, len(train_data) // args.bptt, lr,
                      elapsed * 1000 / args.log_interval, cur_loss, math.exp(cur_loss)))
            total_loss = 0.
            start_time = time.time()

# Loop over epochs.
lr = args.lr
best_val_loss = None
no_improvement = 0

# At any point you can hit Ctrl + C to break out of training early.
if not args.test and not args.interact:
    try:
        for epoch in range(1, args.epochs+1):
            epoch_start_time = time.time()
            train()
            val_loss = evaluate(val_data)
            print('-' * 89)
            print('| end of epoch {:3d} | time: {:5.2f}s | valid loss {:5.2f} | '
                  'valid ppl {:8.2f}'.format(epoch, (time.time() - epoch_start_time),
                                             val_loss, math.exp(val_loss)))
            print('-' * 89)
            # Save the model if the validation loss is the best we've seen so far.
            if not best_val_loss or val_loss < best_val_loss:
                no_improvement = 0
                with open(args.model_file, 'wb') as f:
                    torch.save(model, f)
                    best_val_loss = val_loss
            else:
                # Anneal the learning rate if no more improvement in the validation dataset.
                no_improvement += 1
                if no_improvement >= 3:
                    print('Covergence achieved! Ending training early')
                    break
                lr /= 4.0
    except KeyboardInterrupt:
        print('-' * 89)
        print('Exiting from training early')
else:
    # Load the best saved model.
    with open(args.model_file, 'rb') as f:
        if args.cuda:
            model = torch.load(f).to(device)
        else:
            model = torch.load(f, map_location='cpu')

        if args.init is not None:
            if args.init != -1:
                model.set_parameters(args.init)
            else:
                model.randomize_parameters()

        # after load the rnn params are not a continuous chunk of memory
        # this makes them a continuous chunk, and will speed up forward pass
        if isinstance(model, torch.nn.DataParallel):
            # if multi-gpu, access real model for testing
            model = model.module
        model.rnn.flatten_parameters()

    # Run on test data.
    if args.interact:
        # First fix Python 2.x input command
        try:
            input = raw_input
        except NameError:
            pass

        n_rnn_param = sum([p.nelement() for p in model.rnn.parameters()])
        n_enc_param = sum([p.nelement() for p in model.encoder.parameters()])
        n_dec_param = sum([p.nelement() for p in model.decoder.parameters()])

        print('#rnn params = {}'.format(n_rnn_param))
        print('#enc params = {}'.format(n_enc_param))
        print('#dec params = {}'.format(n_dec_param))


        # Then run interactively
        print('Running in interactive mode. Ctrl+c to exit')
        if '<unk>' not in corpus.dictionary.word2idx:
            print('WARNING: Model does not have unk probabilities.')
        try:
            while True:
                instr = input('Input a sentence: ')
                test_sents, test_data = corpus.online_tokenize_with_unks(instr)
                try:
                    test_evaluate(test_sents, test_data)
                except:
                    print("RuntimeError: Most likely one of the input words was out-of-vocabulary.")
                    print("    Retrain the model with\
                            A) explicit '<unk>'s in the training set\n    \
                            or B) words in validation that aren't present in training.")
                if args.adapt:
                    with open(args.adapted_model, 'wb') as f:
                        torch.save(model, f)
        except KeyboardInterrupt:
            print(' ')
    else:
        if args.multisentence_test:
            test_loss = test_evaluate(None, test_data)
        else:
            test_loss = test_evaluate(test_sents, test_data)
        if args.adapt:
            with open(args.adapted_model, 'wb') as f:
                torch.save(model, f)
    if not args.interact and not args.nopp:
        print('=' * 89)
        print('| End of testing | test loss {:5.2f} | test ppl {:8.2f}'.format(
            test_loss, math.exp(test_loss)))
        print('=' * 89)
