import glob
from statistics import mean

class Entry: 

    def __init__(self, surps):

        self.high_sg = float(surps[0])
        self.low_sg = float(surps[1])
        self.low_pl = float(surps[2])
        self.high_pl = float(surps[3])

path = 'results/'

langs = ['EN', 'ES']

'''
Andrew had dinner yesterday with the nephew of the teachers that was
Andrew had dinner yesterday with the nephews of the teacher that was
Andrew had dinner yesterday with the nephew of the teachers that were
Andrew had dinner yesterday with the nephews of the teacher that were
'''

en_exps = ['replication', 'extension', 'ic', 'rc']
es_exps = ['replication', 'extension']



for lang in langs:

    files = glob.glob(path+lang+'/*')
    if lang == 'EN': 
        exps = en_exps
    else:
        exps = es_exps

    for exp in exps:
        red_files = list(filter(lambda x: exp in x, files))
        print(red_files)
        entries = []
        for f in red_files:
            data = open(f, 'r')
            data.readline()
            sentID = 0
            last_line = None
            surps = []
            for line in data:
                line = line.strip().split()
                cur_ID = int(line[1])
                if cur_ID != sentID:
                    sentID = cur_ID
                    surp = last_line[4]
                    surps.append(surp)
                    if len(surps) == 4:
                        entries.append(Entry(surps))
                        surps = []
                last_line = line

            surps.append(surp)
            if len(surps) == 4:
                entries.append(Entry(surps))
            data.close()

        print(exp)
        #Get distros
        HIGH_SG = mean(list(map(lambda x: x.high_sg, entries)))
        LOW_SG = mean(list(map(lambda x: x.low_sg, entries)))
        HIGH_PL = mean(list(map(lambda x: x.high_pl, entries)))
        LOW_PL = mean(list(map(lambda x: x.low_pl, entries)))
        print('\tHIGH SG: ', HIGH_SG)
        print('\tLOW SG: ', LOW_SG)
        print('\tHIGH PL: ', HIGH_PL)
        print('\tLOW PL: ', LOW_PL)
