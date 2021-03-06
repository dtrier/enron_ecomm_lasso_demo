import pickle
import nltk
import gensim
import functools
import pandas as pd
import scipy
import sklearn
import sys

def remove_proper_nouns(string):
    list_of_words = string.split()
    tagged_low = nltk.tag.pos_tag(list_of_words)
    removed_proper_nouns = list(filter(lambda x: x[1] != 'NNP', tagged_low))
    untagged_low = list(map(lambda x: x[0], removed_proper_nouns))
    return " ".join(untagged_low)

def preprocess(series):

    removed_proper_nouns = series.astype(str).apply(remove_proper_nouns)
    CUSTOM_FILTERS = [lambda x: x.lower(), 
                      gensim.parsing.preprocessing.strip_tags, 
                      gensim.parsing.preprocessing.strip_punctuation]

    preprocessing = gensim.parsing.preprocess_string
    preprocessing_filters = functools.partial(preprocessing, filters=CUSTOM_FILTERS)
    removed_punctuation = removed_proper_nouns.apply(preprocessing)

    stopword_remover = gensim.parsing.preprocessing.remove_stopwords
    stopword_remover_list = lambda x: list(map(stopword_remover, x))
    cleaned = removed_punctuation.apply(stopword_remover_list)

    filter_short_words = lambda x: list(filter(lambda y: len(y) > 1, x))
    cleaned = cleaned.apply(filter_short_words)

    filter_non_alpha = lambda x: list(filter(lambda y: y.isalpha(), x))
    cleaned = cleaned.apply(filter_non_alpha)
    
    stemmer = nltk.stem.porter.PorterStemmer()
    list_stemmer = lambda x: list(map(lambda y: stemmer.stem(y), x))
    cleaned = cleaned.apply(list_stemmer)

    return cleaned

def pad_sparse_matrix(sp_mat, length, width):
    sp_data = (sp_mat.data, sp_mat.indices, sp_mat.indptr)
    padded = scipy.sparse.csr_matrix(sp_data, shape=(length, width))
    return padded

#modelop.init
def begin():
    global lasso_model_artifacts 
    lasso_model_artifacts = pickle.load(open('lasso_model_artifacts.pkl', 'rb'))
    nltk.download('averaged_perceptron_tagger')
    pass

#modelop.score
def action(x):
    lasso_model = lasso_model_artifacts['lasso_model']
    dictionary = lasso_model_artifacts['dictionary']
    threshold = lasso_model_artifacts['threshold']
    tfidf_model = lasso_model_artifacts['tfidf_model']
    
    x = pd.DataFrame(x, index=[0])
    sys.stdout.flush()
    cleaned = preprocess(x.content)
    corpus = cleaned.apply(dictionary.doc2bow)
    corpus_sparse = gensim.matutils.corpus2csc(corpus).transpose()
    corpus_sparse_padded = pad_sparse_matrix(sp_mat = corpus_sparse, 
                                             length=corpus_sparse.shape[0], 
                                             width = len(dictionary))
    tfidf_vectors = tfidf_model.transform(corpus_sparse_padded)

    probabilities = lasso_model.predict_proba(tfidf_vectors)[:,1]

    predictions = pd.Series(probabilities > threshold, index=x.index).astype(int)
    output = pd.concat([x, predictions], axis=1)
    output.columns = ['id', 'content', 'prediction']
    output = output.to_dict(orient='records')
    yield output
    
def get_shap():
    return {
        "strategi": 3.2520682958749694,
        "indic": 0.7102795675925868,
        "net": 0.3541640953338466,
        "research": 2.340609152949877,
        "market": 1.6368844559196445,
        "version": 1.9101731885557005,
        "good": 1.3562284993616274,
        "mail": 0.6928553560354906,
        "bid": 2.8162293879415072,
        "data": 3.387712516393189,
        "report": 0.47704432407553465,
        "greet": 2.754767300818468,
        "said": 4.54813893155902,
        "approach": 5.799971287318539,
        "develop": 3.3643937399880004,
        "law": 2.196729052019291,
        "normal": 2.681564509767407,
        "pocket": 1.2258033392225045,
        "trader": 0.8864414506427811,
        "trigger": 1.9309807702640416,
        "label": 2.885248298256796,
        "softwar": 1.995336285501284
    }

def get_bias():
    return {
        "attributeAudited": "Gender",
        "referenceGroup": "Male",
        "fairnessThreshold": "80%",
        "fairnessMeasures": [
            {
                "label": "Equal Parity",
                "result": "Failed",
                "group": "Female",
                "disparity": 0.75
            },
            {
                "label": "Proportional Parity",
                "result": "Passed",
                "group": None,
                "disparity": 1.05
            },
            {
                "label": "False Positive Rate Parity",
                "result": "Passed",
                "group": "Female",
                "disparity": 0.97
            },
            {
                "label": "False Discovery Rate Parity",
                "result": "Passed",
                "group": "Female",
                "disparity": 0.88
            },
            {
                "label": "False Negative Rate Parity",
                "result": "Passed",
                "group": "Female",
                "disparity": 1.05
            },
            {
                "label": "False Omission Rate Parity",
                "result": "Passed",
                "group": "Female",
                "disparity": 0.93
            }
        ]
        }

def matrix_to_dicts(matrix, labels):
    cm = []
    for idx, label in enumerate(labels):
        cm.append(dict(zip(labels, matrix[idx, :].tolist())))
    return cm

#modelop.metrics
def metrics(x):
    lasso_model = lasso_model_artifacts['lasso_model']
    dictionary = lasso_model_artifacts['dictionary']
    threshold = lasso_model_artifacts['threshold']
    tfidf_model = lasso_model_artifacts['tfidf_model']

    actuals = x.flagged
    
    cleaned = preprocess(x.content)
    corpus = cleaned.apply(dictionary.doc2bow)
    corpus_sparse = gensim.matutils.corpus2csc(corpus).transpose()
    corpus_sparse_padded = pad_sparse_matrix(sp_mat = corpus_sparse, 
                                             length=corpus_sparse.shape[0], 
                                             width = len(dictionary))
    tfidf_vectors = tfidf_model.transform(corpus_sparse_padded)

    probabilities = lasso_model.predict_proba(tfidf_vectors)[:,1]

    predictions = pd.Series(probabilities > threshold, index=x.index).astype(int) 
    
    confusion_matrix = sklearn.metrics.confusion_matrix(actuals, predictions)
    fpr,tpr,thres = sklearn.metrics.roc_curve(actuals, probabilities)

    auc = sklearn.metrics.auc(fpr, tpr)
    f2 = sklearn.metrics.fbeta_score(actuals, predictions, beta=2)

    ROC = [{'fpr': x[0], 'tpr':x[1]} for x in list(zip(fpr, tpr))]
    labels = ['Compliant', 'Non-Compliant']
    cm = matrix_to_dicts(confusion_matrix, labels)
    shap = get_shap()
    bias = get_bias()
    test_results = dict(ROC=ROC,
                   auc=auc,
                   f2_score=f2,
                   confusion_matrix=cm,
                   bias=bias,
                   shap=shap
                   )    

    yield test_results

def remove_proper_nouns(string):
    list_of_words = string.split()
    tagged_low = nltk.tag.pos_tag(list_of_words)
    removed_proper_nouns = list(filter(lambda x: x[1] != 'NNP', tagged_low))
    untagged_low = list(map(lambda x: x[0], removed_proper_nouns))
    return " ".join(untagged_low)

#modelop.train
def train(data):
    y_train = data.flagged
    removed_proper_nouns = data.content.astype(str).apply(remove_proper_nouns)
    CUSTOM_FILTERS = [lambda x: x.lower(), 
                  gensim.parsing.preprocessing.strip_tags, 
                  gensim.parsing.preprocessing.strip_punctuation]
    removed_punctuation = removed_proper_nouns.apply(functools.partial(gensim.parsing.preprocess_string, filters=CUSTOM_FILTERS))

    stemmer = nltk.stem.porter.PorterStemmer()
    #Remove stop words, words of length less than 2, and words with non-alphabet characters.
    cleaned = removed_punctuation.apply(lambda x: list(map(gensim.parsing.preprocessing.remove_stopwords, x)))
    cleaned = cleaned.apply(lambda x: list(filter(lambda y: len(y) > 1, x)))
    cleaned = cleaned.apply(lambda x: list(filter(lambda y: y.isalpha(), x)))
    cleaned = cleaned.apply(lambda x: list(map(stemmer.stem, x)))

    #Create a dictionary (key, value pairs of ids with words which appear in the corpus.
    dictionary = gensim.corpora.dictionary.Dictionary(documents=cleaned)
    dictionary.filter_extremes(no_below=5, no_above=0.4)

    # Produce a sparse bag-of-words matrix from the word-document frequency counts
    corpus = cleaned.apply(dictionary.doc2bow).to_list()
    corpus_sparse = gensim.matutils.corpus2csc(corpus).transpose()

    # Train a tf-idf transformer and transform the training data
    tfidf_model = sklearn.feature_extraction.text.TfidfTransformer()
    train_tfidf = tfidf_model.fit_transform(train_corpus_sparse)

    # Define and fit a logistic regression model
    logreg = sklearn.linear_model.LogisticRegression(penalty='l1', class_weight='balanced', max_iter=2500, random_state=740189)
    logreg_model = logreg.fit(X=train_tfidf, y=y_train)

    lasso_model_artifacts = dict(lasso_model = logreg_model, 
                             dictionary = dictionary, 
                             tfidf_model = train_tfidf, 
                             threshold = thresh)
    pickle.dump(lasso_model_artifacts, open('lasso_model_artifacts.pkl', 'wb'))
    pass

