from time import time
from math import sqrt

import numpy as np

import pickle
from constants import *

from os.path import exists

### I/O, formatting & parsing

def streamfile(filename, convert=float):
    with open(filename, "r") as file:
        for line in file.readlines():
            yield convert(line)

def no_columns(filename, convert=float):
    with open(filename, "r") as file:
        return len(splitline(file.readline(), convert))

def load(filename, convert=float, dtype=float):
    return np.fromiter(streamfile(filename,convert), dtype=dtype)

def loadcsv(filename, convert=float, dtype=float):
    nb_hours = no_columns(filename)
    return np.fromiter(streamfile(filename, lambda line: splitline(line, convert)), dtype=np.dtype((dtype, nb_hours)))

def splitline(line, convert):
    return list(map(convert, (s for s in line.strip().split(",") if s and s != '\n')))

def load_list(filename, convert=float):
    return list(streamfile(filename,convert))

def loadcsv_lists(filename, convert=float):
    return load_list(filename, lambda line: splitline(line, convert) )

def loadcsvdict(filename, converthashable=[int,int], convertdatapoint=float):
    data = {}
    for line in load(filename, lambda line: splitline(line, str) ):
        value = [convertdatapoint(x) for x in line[len(converthashable):]]
        data[tuple(converthashable[i](line[i]) for i in range(len(converthashable)))] = value
    return data

def write2file(filename, function, *args):
    with open(filename, 'w') as outfile:
        function(*args, f=outfile)

def write2csv(filename, mylist):
    with open(filename, 'w') as outfile:
        for elem in mylist:
            print(elem, file=outfile)
                
def write2dmatrix2csv(filename, matrix):
    with open(filename, 'w') as outfile:
        for line in matrix:
            print(*line, sep=',', file=outfile)

### math utils

def mean(filename):
    data = load(filename)
    return sum(data)/len(data)

# column-wise aggregate function
def aggregate(matrix):
    return [sum(matrix[h][t] for h in range(len(matrix))) for t in range(len(matrix[0]))]

# average, this function can be used on any iterable
def avg(L): 
    sum_x, n = 0, 0
    for x in L:
        sum_x += x
        n += 1
    return sum_x / n

# standard deviation, this function can be used on any iterable
def std(L):
    a = avg(L)
    return sqrt(avg([(x-a)**2 for x in L]))

### time utils

def timecode(f):
    t = time()
    x = f()
    s = time()-t
    print("Execution time:", s//60, "minutes and", round(s%60,3), "seconds.")
    return x

def timecodes(function_list):
    times = []
    X = []
    for f in function_list:
        t = time()
        X += [f()]
        times += [round(time()-t,2)]
    print(f"Execution time: min {min(times)}, max {max(times)}, avg {avg(times)} seconds.")
    return X

### default electricitity prices

def ecost(price, el_in, el_out,
          tax=TAX_DEFAULT, el_tax=EL_TAX_DEFAULT, el_net=EL_NET_DEFAULT):
	return el_in*(price*tax + el_tax) - el_out*(price + el_net)

def total_cost(prices, elin, elout):
	return sum([ecost(p, e1, e2) for p, e1, e2 in zip(prices, elin, elout)])
    
### old utils

def consh(cons, h):
    return [cons[t][h] for t in range(len(cons))]

def cons2newformat(cons):
    return [consh(cons,h) for h in range(len(cons[0]))]

def avgabserrors(table, windowsize, predictor):
    errors = [0]*windowsize
    for t0 in range(len(table)-windowsize):
        for i in range(windowsize):
            errors[i] += abs(table[t0+i]-predictor(table, t0+i, t0, t0+windowsize))
    return [err/((len(table)-windowsize)) for err in errors]

def avgtables(tables):
    return [sum(table[i] for table in tables)/len(tables) for i in range(len(tables[0]))]

### load pre-parsed file  --  use with caution if the class is modified

def savedump(myobj, filename):
    with open(filename,'wb') as f:
        pickle.dump(myobj, f)

def loaddump(filename):
    with open(filename,'rb') as f:
        return pickle.load(f)

def load_or_precompute(filepath, compute_func):
    if exists(filepath):
        return loaddump(filepath)
    obj = compute_func()
    savedump(obj, filepath)
    return obj

