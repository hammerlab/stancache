from fnmatch import fnmatch
import ntpath
import re
import patsy
import seaborn as sns
import pandas as pd
import numpy as np
from . import seed
import os
import logging
from matplotlib import pyplot as plt
logger = logging.getLogger(__name__)

def filter_stan_summary(stan_fit, pars):
    fitsum = stan_fit.summary(pars=pars)
    res = pd.DataFrame(fitsum['summary'], columns=fitsum['summary_colnames'], index=fitsum['summary_rownames'])
    return res.loc[:,['mean','se_mean','sd','2.5%','50%','97.5%','Rhat']]


def print_stan_summary(stan_fit, pars):
    print(filter_stan_summary(stan_fit=stan_fit, pars=pars).to_string())


def plot_stan_summary(stan_fit, pars, metric='Rhat'):
    df = filter_stan_summary(stan_fit=stan_fit, pars=pars)
    sns.distplot(df[metric])


def patsy_helper_nointercept(df, formula):
    model_frame = patsy.dmatrix('{} - 1'.format(formula), data=df, return_type='dataframe')
    if 'Intercept' in model_frame.columns:
        model_frame.drop('Intercept', axis=1, inplace=True)
    return model_frame


def is_field_unique_by_group(df, field_col, group_col):
    ''' Determine if field is constant by group in df
    '''
    def num_unique(x):
        return len(pd.unique(x))
    num_distinct = df.groupby(group_col)[field_col].agg(num_unique)
    return all(num_distinct == 1)

    
def _list_files_in_path(path, pattern="*.stan"):
    """
    indexes a directory of stan files
    returns as dictionary containing contents of files
    """

    results = []
    for dirname, subdirs, files in os.walk(path):
        for name in files:
            if fnmatch(name, pattern):
                results.append(os.path.join(dirname, name))
    return(results)


def _find_directory(d, description=''):
    my_dir = d
    _this_dir = os.getcwd()
    if not os.path.exists(my_dir):
        my_dir = os.path.join(_this_dir, d)
    if not os.path.exists(my_dir):
        raise ValueError('{} directory ({}) not found'.format(description, d))
    return my_dir


def _make_model_dict(model_dir, pattern="*.stan"):
    model_files = _list_files_in_path(path=model_dir, pattern=pattern)
    res = dict()
    [res.update({ntpath.basename(model_file): model_file}) for model_file in model_files]
    return res


def get_model_file(model_name, model_dir='models', pattern="*.stan"):
    clean_model_dir = _find_directory(d=model_dir, description='model')
    model_files = _make_model_dict(clean_model_dir, pattern=pattern)
    if model_name in model_files.keys():
        model_file = model_files[model_name]
    else:
        matching_files = [mfile for (mname, mfile) in model_files.items()
                      if re.match(string=mname, pattern='{}\w'.format(model_name))]
        if len(matching_files)==1:
            model_file = matching_files[0]
        elif len(matching_files)>1:
            logger.warning('Multiple files match given string. Selecting the first')
            model_file = matching_files[0]
        else:
            logger.warning('No files match given string.')
            logger.debug('Files searched include: {}'.format('\n'.join(model_files.keys())))
            model_file = None
    if not model_file:
        raise ValueError('Model could not be identified: {}'.format(model_name))
    return model_file

