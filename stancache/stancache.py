import os
import pickle
import dill
import pystan
import hashlib
import base64
import logging 
from fnmatch import fnmatch
import ntpath
from . import seed
from time import time
from datetime import timedelta
import pandas as pd
import re
import Cython
from . import config
import types
import numpy as np
import xxhash
import sys

logger = logging.getLogger(__name__)

def _mkdir_if_not_exists(path):
    try:
        os.mkdir(path)
    except:
        pass


def _make_digest_dataframe(item):
    index = tuple(item.index)
    columns = tuple(item.columns)
    values = tuple(tuple(x) for x in item.values)
    s = _pickle_dumps_digest(tuple([index, columns, values]))
    return s


def _xxhash_item(item):
    h = xxhash.xxh64(item)
    s = h.intdigest()
    return s

def _pickle_dumps_digest(item):
    s = pickle.dumps(item)
    h = _digest(s)
    return h

def _digest(s):
    h = int(hashlib.sha1(s).hexdigest(), 16) % (10 ** 11)
    return h

def _make_digest_dict(k, prefix=''):
    result = dict()
    if len(k) == 0:
        return None
    for (key, item) in sorted(k.items()):
        pre_key = '{}{}'.format(prefix, key)
        if isinstance(item, str) and len(item) <= 11:
            logger.debug('processing item ({}) as str'.format(pre_key))
            s = re.sub(string=item, pattern='[\.\-]', repl='_')
            result.update({pre_key: s})
        elif isinstance(item, int) and len(str(item)) <= 11:
            logger.debug('processing item ({}) as int'.format(pre_key))
            s = re.sub(string=str(item), pattern='[\.\-]', repl='_')
            result.update({pre_key: s})
        elif isinstance(item, dict):
            logger.debug('processing item ({}) as dict'.format(pre_key)) 
            item = dict(sorted(item.items()))
            s = _make_digest(item, prefix=key+'-')
            result.update({pre_key: _digest(s.encode())})
        elif isinstance(item, pd.DataFrame):
            logger.debug('processing item ({}) as dataframe'.format(pre_key))
            s = _make_digest_dataframe(item)
            result.update({pre_key: s})
        elif isinstance(item, pd.Series):
            logger.debug('processing item ({}) as pd.Series'.format(pre_key))
            s = _xxhash_item(item.values)
            result.update({pre_key: s})
        elif isinstance(item, np.ndarray):
            logger.debug('processing item ({}) as np.ndarray'.format(pre_key))
            s = _xxhash_item(item)
            result.update({pre_key: s})
        elif isinstance(item, types.FunctionType):
            logger.debug('processing item ({}) as function'.format(pre_key))
            try:
                s = _pickle_dumps_digest(str(dill.source.getsource(item)))
            except:
                s = 'unhashable'
            result.update({pre_key: s})
        else:
            try:
                logger.debug('processing item ({}) as other (using xxhash)'.format(pre_key))
                s = _xxhash_item(item)
            except:
                logger.debug('processing item ({}) as other (using pickle)'.format(pre_key))
                s = _pickle_dumps_digest(item)
            logger.debug('note: item ({}) is of type: {}'.format(pre_key, item.__class__))
            result.update({pre_key: s})
    return result
    
def _make_digest(k, **kwargs):
    """
    Creates a digest suitable for use within an :class:`phyles.FSCache`
    object from the key object `k`.

    >>> adict = {'a' : {'b':1}, 'f': []}
    >>> make_digest(adict)
    'a2VKynHgDrUIm17r6BQ5QcA5XVmqpNBmiKbZ9kTu0A'
    """
    result = list()
    result_dict = _make_digest_dict(k, **kwargs)
    if result_dict is None:
        return 'default'
    else: 
        for (key, h) in sorted(result_dict.items()):
            result.append('{}_{}'.format(key, h))
        return '.'.join(result)

def _get_cache_dir(cache_dir=None):
    if cache_dir is None:
        cache_dir = config.get_setting_value('CACHE_DIR')
        logger.debug('cache_dir set to {}'.format(cache_dir))
        _mkdir_if_not_exists(cache_dir)
    return cache_dir
    

def cached_model_file(model_name='anon_model', file=None, model_code=None, cache_dir=None,
                      fit_cachefile=None, include_prefix=False):
    ''' Given model name & stan model code/file, compute path to cached stan fit
        
        if include_prefix, returns (model_prefix, model_cachefile)
    '''
    cache_dir = _get_cache_dir(cache_dir)
    model_name = _sanitize_model_name(model_name)
    ## compute model prefix
    if file:
        model_code = _read_file(file)
    if model_code:
        model_prefix = '.'.join([model_name, _make_digest(dict(model_code=model_code,
                                                               pystan=pystan.__version__,
                                                               cython=Cython.__version__))])
    else: ## handle case where no model code given
        if file is not None:
            logger.info('Note - no model code detected from given file: {}'.format(file))
        else:
            logger.info('Note - no model code detected (neither file nor model_code given)')
    ## parse model_prefix from fit_cachefile if given
    if fit_cachefile:
        # if necessary, impute cache_dir from filepath
        if fit_cachefile != os.path.basename(fit_cachefile):
            cache_dir, fit_cachefile = os.path.split(os.path.abspath(fit_cachefile))
        # if fit_cachefile given, parse to get fit_model_prefix
        fit_model_prefix = re.sub(string=os.path.basename(fit_cachefile), pattern='(.*).stanfit.*', repl='\\1')
        if model_code:
            if fit_model_prefix != model_prefix:
                logger.warning('Computed model prefix does not match that used to estimate model. Using prefix matching fit_cachefile')
        model_prefix = fit_model_prefix
    # compute path to model cachefile
    model_cachefile = '.'.join([model_prefix, 'stanmodel', 'pkl'])
    if include_prefix:
        return model_prefix, model_cachefile
    return model_cachefile


def cached_stan_file(model_name='anon_model', file=None, model_code=None,
                  cache_dir=None, fit_cachefile=None, cache_only=None, force=False,
                  include_modelfile=False, prefix_only=False,
                  **kwargs
                  ):
    ''' Given inputs to cached_stan_fit, compute pickle file containing cached fit
    '''
    model_prefix, model_cachefile = cached_model_file(model_name=model_name, file=file, model_code=model_code,
                                                      cache_dir=cache_dir, fit_cachefile=fit_cachefile, include_prefix=True)
    if not fit_cachefile:
        fit_cachefile = '.'.join([model_prefix, 'stanfit', _make_digest(dict(**kwargs)), 'pkl'])
    if include_modelfile:
        return model_cachefile, fit_cachefile
    if prefix_only:
        fit_cachefile = re.sub(string=fit_cachefile, pattern='.pkl$', repl='')
    return fit_cachefile


def _sanitize_model_name(model_name):
    if model_name:
        model_name = re.sub(string=model_name, pattern='[\.\-]', repl='_')
    return model_name

def _get_model_code(model_code=None, file=None):
    ## compute model prefix
    if file:
        model_code = _read_file(file)
    if not model_code:
        if file is not None:
            logger.info('Note - no model code detected from given file: {}'.format(file))
        else:
            logger.info('Note - no model code detected (neither file nor model_code given)')
    return model_code

def _cached_stan_fit(model_name='anon_model', file=None, model_code=None,
                    force=False, cache_dir=None, cache_only=None, 
                     fit_cachefile=None, **kwargs):
    ''' Cache fit stan model, by storing pickled objects in filesystem
    
    per following warning:
      07: UserWarning: Pickling fit objects is an experimental feature!
        The relevant StanModel instance must be pickled along with this fit object.
        When unpickling the StanModel must be unpickled first.
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)
    '''
    if fit_cachefile and cache_only is None:
        cache_only = True
    model_cachefile, fit_cachefile = cached_stan_file(model_name=model_name, file=file, model_code=model_code,
                                                      cache_dir=cache_dir, fit_cachefile=fit_cachefile,
                                                      include_modelfile=True, **kwargs)
    cache_dir = _get_cache_dir(cache_dir)
    model_name = _sanitize_model_name(model_name)
    model_code = _get_model_code(model_code=model_code, file=file)
    logger.info('Step 1: Get compiled model code, possibly from cache')
    stan_model = cached(func=pystan.StanModel,
                         cache_filename=model_cachefile,
                         model_code=model_code,
                         cache_dir=cache_dir,
                         model_name=model_name,
                         cache_only=cache_only,
                         force=force)
    
    ## either pull fitted model from cache, or fit model
    logger.info('Step 2: Get posterior draws from model, possibly from cache')
    fit = cached(func=stan_model.sampling,
                  cache_filename=fit_cachefile,
                  cache_dir=cache_dir,
                  force=force,
                  cache_only=cache_only,
                  **kwargs)
    return fit


def _read_file(filepath):
    with open(filepath, 'r') as myfile:
        data = myfile.read()
    return data


def cached_stan_fit(iter=2000, chains=4, seed=None, *args, **kwargs):
    arglist = list(*args)
    if len(arglist)>0:
        raise ValueError('unnamed args not permitted')
    if seed is None:
        seed = config.get_setting_value('SEED')
    return _cached_stan_fit(seed=seed, iter=iter, chains=chains, **kwargs)


def cached(func, file_prefix='cached', cache_filename=None,
            cache_dir=None, force=False, cache_only=False,
            compute_hash=True, *args, **kwargs):
    cache_dir = _get_cache_dir(cache_dir)
    if not cache_filename:
        arglist = list(*args)
        if len(arglist)>0:
            raise ValueError('unnamed args not permitted')
        cache_filename = '.'.join([func.__name__, file_prefix, _make_digest(dict(**kwargs)), 'pkl'])
    logger.info('{}: cache_filename set to {}'.format(func.__name__, cache_filename))
    cache_filepath = os.path.join(cache_dir, cache_filename)
    logger.debug('{}: cache_filepath set to {}'.format(func.__name__, cache_filepath))
    if not force and os.path.exists(cache_filepath):
        try:
            logger.info('{}: Loading result from cache'.format(func.__name__))
            res = pickle.load(open(cache_filepath, 'rb'))
        except ImportError as e:
            print('{}: Error loading from cache: {}'.format(func.__name__, str(e)))
        else:
            return res
    if cache_only:
        raise ValueError('{}: Cachefile does not exist and cache_only == True. Exiting with failure.'.format(func.__name__))
    logger.info('{}: Starting execution'.format(func.__name__))
    start = time()
    res = func(**kwargs)
    end = time()
    elapsed = str(timedelta(seconds=end-start))
    logger.info('{}: Execution completed ({} elapsed)'.format(func.__name__, elapsed))
    try:
        _mkdir_if_not_exists(cache_dir)
        logger.info('{}: Saving results to cache'.format(func.__name__))
        pickle.dump(res, open(cache_filepath, 'wb'), pickle.HIGHEST_PROTOCOL)     
    except IOError as e:
        logger.warning("{}: I/O error saving to cache ({}): {}".format(func.__name__, e.errno, e.strerror))
    except:
        logger.warning('{}: Unexpected error saving to cache: {}'.format(func.__name__, sys.exc_info()[0]))
    return res

