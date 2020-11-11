# AmbiAttach
Project for interpreting RNN LM syntactic knowledge using ambiguous relative clause attachment in English and Spanish. 

### Dependencies
Requires the following python packages (available through pip):
* [pytorch](https://pytorch.org/) v1.0.0

### Quick Usage
One English and one Spanish model are already in the models directory (due to space). The others can be found [here](https://zenodo.org/record/3778994#.X6wfxnVKj3A). 

To get by-word compelxity results

        python run_test.py [es|en] [0-5]

The first arugment corresponds to the language and the second to the model you wish to evaluate. The complexity 
metrics are derived from the repository [neural-complexity](https://github.com/vansky/neural-complexity). For ease of use I have included the necessary files here, but
see that repo for more details. 

### Extra Details

As mentioned in the Quick Usage, the models used in the paper (English, Spanish, and synthetic) can be found on our Zenodo
[repo](https://zenodo.org/record/3778994#.X6wfxnVKj3A). Additionally, the raw results from each of the models is given (if you want to save compute time, especially for the 
larger stimuli). 

### References

Forrest Davis and Marten van Schijndel. ["Recurrent Neural Networks Always learn English-Like Relative Clause Attachment."](https://www.aclweb.org/anthology/2020.acl-main.179/) In Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics (ACL 2020). 2020.
