import subprocess
import sys
import os

#Run script with test sentences 
def generate_results(sentsFile, dataFile, lang, modelNUM):

    if lang == 'en':
        if modelNUM == 0:
            modelFile = 'models/en_models/hidden650_batch128_dropout0.2_lr20.0.pt'
        if modelNUM == 1:
            modelFile = 'models/en_models/en_hidden650_batch128_dropout0.2_lr20_1.pt'
        if modelNUM == 2:
            modelFile = 'models/en_models/en_hidden650_batch128_dropout0.2_lr20_2.pt'
        if modelNUM == 3:
            modelFile = 'models/en_models/en_hidden650_batch128_dropout0.2_lr20_3.pt'
        if modelNUM == 4:
            modelFile = 'models/en_models/en_hidden650_batch128_dropout0.2_lr20_4.pt'
    if lang == 'es':
        if modelNUM == 0:
            modelFile = 'models/es_models/es_hidden650_batch64_dropout0.2_lr20_0.pt'
        if modelNUM == 1:
            modelFile = 'models/es_models/es_hidden650_batch64_dropout0.2_lr20_1.pt'
        if modelNUM == 2:
            modelFile = 'models/es_models/es_hidden650_batch64_dropout0.2_lr20_2.pt'
        if modelNUM == 3:
            modelFile = 'models/es_models/es_hidden650_batch64_dropout0.2_lr20_3.pt'
        if modelNUM == 4:
            modelFile = 'models/es_models/es_hidden650_batch64_dropout0.2_lr20_4.pt'

    subprocess.run(["./test_results.sh", modelFile, sentsFile, lang, dataFile])



if __name__ == "__main__":
    
    if len(sys.argv) != 3:
        print('INCORRECT USAGE: \n\t python run_test.py [es|en] [0-5]')
        sys.exit()

    lang = sys.argv[1]
    model_num = int(sys.argv[2])

    if lang == 'en':

        ##### REPLICATE ######
        sentsFile = 'stimuli/en_replication_stimuli'
        dataFile = 'results/EN/en_'+str(model_num)+'_replication_measures'
        generate_results(sentsFile, dataFile, lang, model_num)


        ##### EXTENSION ######
        sentsFile = 'stimuli/en_extension_stimuli'
        dataFile = 'results/EN/en_'+str(model_num)+'_extension_measures'
        generate_results(sentsFile, dataFile, lang, model_num)

        ##### IC ######
        sentsFile = 'stimuli/en_ic_stimuli'
        dataFile = 'results/EN/en_'+str(model_num)+'_ic_measures'
        generate_results(sentsFile, dataFile, lang, model_num)

        ##### RC ######
        sentsFile = 'stimuli/en_rc_stimuli'
        dataFile = 'results/EN/en_'+str(model_num)+'_rc_measures'
        generate_results(sentsFile, dataFile, lang, model_num)

    if lang == 'es':

        ##### REPLICATE ######
        sentsFile = 'stimuli/es_replication_stimuli'
        dataFile = 'results/ES/es_'+str(model_num)+'_replication_measures'
        generate_results(sentsFile, dataFile, lang, model_num)


        ##### EXTENSION ######
        sentsFile = 'stimuli/es_extension_stimuli'
        dataFile = 'results/ES/es_'+str(model_num)+'_extension_measures'
        generate_results(sentsFile, dataFile, lang, model_num)
