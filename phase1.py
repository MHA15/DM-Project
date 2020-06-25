import pandas as pd
import math
import numpy as np
# from sklearn.model_selection import train_test_split
# from sklearn.linear_model import LinearRegression
# from sklearn.metrics import r2_score
# from sklearn.metrics import mean_squared_error
# from sklearn.metrics import max_error
# from sklearn.model_selection import train_test_split
# from sklearn.linear_model import LinearRegression
# from sklearn.metrics import r2_score
# from sklearn.metrics import mean_squared_error
# from sklearn.metrics import max_error
import seaborn as sns
import matplotlib.pyplot as plt
# from sklearn.experimental import enable_iterative_imputer
# import sklearn.impute as impute
# import pandas_profiling as pp
# from sklearn.linear_model import LinearRegression
# from sklearn.metrics import r2_score
# from sklearn.model_selection import train_test_split
# from sklearn.cluster import DBSCAN
# from scipy import stats
# from sklearn.preprocessing import MinMaxScaler
# import scipy as sp
# from sklearn.preprocessing import RobustScaler
# from mlxtend.frequent_patterns import apriori, association_rules
# from scipy import sparse
import datetime
from os.path import join
from sklearn.metrics import confusion_matrix
from sklearn.ensemble import RandomForestClassifier,BaggingClassifier
from sklearn.metrics import recall_score
from sklearn.metrics import precision_score
from sklearn.model_selection import cross_val_score
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier

DRAW_DIST_PLOT = False
LOG_STEPS = True

# Create dataframes from json files
df_test = pd.read_json(join('.', 'Test_Data.json'), lines=True)
df_train = pd.read_json(join('.', 'Train_Data.json'), lines=True)

baseTimeSpan = pd.Timestamp("2012-01-01 00:00:00+00:00")


def jsonToDataFrame(json):
    res_x = pd.DataFrame()
    res_y = pd.DataFrame()
    res_x["len"] = json.text.agg(len)
    res_x["truncated"] = json.truncated
    res_x["hashtags"] = json.entities.agg(lambda x: len(x["hashtags"]))
    res_x["user_mentions"] = json.entities.agg(lambda x: len(x["user_mentions"]))
    res_x["favorite_count"] = json.favorite_count
    res_x["is_quote_status"] = json.is_quote_status
    res_x["lang"] = json.lang
    # Will be 1 if sensitive, else 0
    res_x["possibly_sensitive"] = json.possibly_sensitive.agg(lambda x: 0 if math.isnan(x) or x == 0 else 1)

    def filledReader(name, defaultValue=None):
        return lambda x: defaultValue if x is None else x[name]

    def booleanToBinary(column):
        return column.apply(lambda x: 0 if not x else 1)

    def userInfoToRes(str, user):
        res_x[str + "__created_at"] = user.agg(filledReader("created_at")).agg(pd.Timestamp).astype(int) \
                                      / (10 ** 9 * 1440 * 60 * 365)  # Account age in years
        res_x[str + "__default_profile_image"] = user.agg(filledReader("default_profile_image", False))
        # remove because nemifahmam chie
        # res[str + "__entities"] = user.agg(filledReader("entities"))
        res_x[str + "__favourites_count"] = user.agg(filledReader("favourites_count"))
        res_x[str + "__followers_count"] = user.agg(filledReader("followers_count"))
        res_x[str + "__following"] = user.agg(filledReader("following", False))
        res_x[str + "__friends_count"] = user.agg(filledReader("friends_count"))
        res_x[str + "__has_extended_profile"] = user.agg(filledReader("has_extended_profile", False))
        res_x[str + "__is_translator"] = user.agg(filledReader("is_translator", False))
        res_x[str + "__lang"] = user.agg(filledReader("lang", ""))
        res_x[str + "__listed_count"] = user.agg(filledReader("listed_count"))
        res_x[str + "__protected"] = user.agg(filledReader("protected", False))
        res_x[str + "__statuses_count"] = user.agg(filledReader("statuses_count"))
        res_x[str + "__verified"] = user.agg(filledReader("verified", False))

    userInfoToRes("current-user", json.user)
    userInfoToRes("original-user", json.retweeted_status.agg(lambda x: None if type(x) is not dict else x["user"]))

    # 1 if the tweet is viral (retweets are above median), 0 if not
    res_y['retweet_count'] = json.retweeted_status.agg(lambda x: None if type(x) is not dict else x["retweet_count"])
    res_y['retweet_count'] = res_y['retweet_count'].agg(lambda x: 1 if x >= res_y['retweet_count'].median() else 0)

    # Change True/False into 0/1
    for (columnName, columnData) in res_x.iteritems():
        columnType = res_x.dtypes[columnName]
        # if columnType == 'object':
        #     print(columnName)

        if columnType == 'float64':
            res_x[columnName] = res_x[columnName].fillna(0.0).astype(int)

        if columnType == 'bool':
            res_x[columnName] = booleanToBinary(res_x[columnName])

        print(columnName, columnType)

    # 1->Short Twee(1-50) / 2->Medium Tweet(50-100) / 3->Long Tweet(100-140)
    res_x['len'] = res_x['len'].agg(lambda x: 1 if x < 51 else (2 if x < 101 else 3))

    # Draws histograms for each column. used for categorizing
    if DRAW_DIST_PLOT:
        for (columnName, columnData) in res_x.iteritems():
            sns.distplot(columnName, kde=False)
            plt.title(columnName)
            plt.show()

    res_x = pd.get_dummies(res_x)
    return res_x, res_y


# Dropping the rows without 'retweet_count'
df_test = df_test[df_test['retweeted_status'].notna()]

X_train, Y_train = jsonToDataFrame(df_train)
if LOG_STEPS:
    print("Train Data Finished!")
X_test, Y_test = jsonToDataFrame(df_test)
if LOG_STEPS:
    print("Test Data Finished!")

# Add the missing columns (all languages)
for (columnName, columnData) in X_train.iteritems():
    if not (columnName in X_test.columns):
        X_test[columnName] = 0

for (columnName, columnData) in X_test.iteritems():
    if not (columnName in X_train.columns):
        X_train[columnName] = 0


# Changing from columns to values
# https://stackoverflow.com/questions/34165731/a-column-vector-y-was-passed-when-a-1d-array-was-expected
Y_train = Y_train.values.ravel()
Y_test = Y_test.values.ravel()

# KNN Model
score_knn = []
weights = ['uniform', 'distance']
for i in np.arange(1, 2, 1):
    for j in np.arange(1, 2, 1):
        for k in weights:
            if LOG_STEPS:
                print("Calculating KNN Score with n =", i, ", p =", j, ", weights =", k)
            knn = KNeighborsClassifier(n_neighbors=i, p=j, weights=k)
            knn.fit(X_train, Y_train)
            score_knn.append([i, j, k, np.mean(cross_val_score(knn, X_train, Y_train, scoring='recall', cv=5))])

# Calculating the best paratemers
score_knn = pd.DataFrame(score_knn)
score_knn = score_knn.sort_values(by=3, ascending=False)

print("The best n_neigbors:", score_knn.iat[0, 0])
print("The best p:", score_knn.iat[0, 1])
print("The best weights:", score_knn.iat[0, 2], '\n')

knn = KNeighborsClassifier(n_neighbors=score_knn.iat[0, 0], p=score_knn.iat[0, 1], weights=score_knn.iat[0, 2])

knn.fit(X_train, Y_train)

print("KNN Score:", knn.score(X_test, Y_test))
print("Recall Score:", recall_score(Y_test, knn.predict(X_test)))
print("Precision Score:", precision_score(Y_test, knn.predict(X_test)))
print("Confusion Matrix:\n", confusion_matrix(Y_test, knn.predict(X_test)), "\n\n")

