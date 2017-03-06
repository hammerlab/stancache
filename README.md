[![Build Status](https://travis-ci.org/hammerlab/stancache.svg?branch=master)](https://travis-ci.org/hammerlab/stancache) 
[![Coverage Status](https://img.shields.io/coveralls/hammerlab/stancache.svg)](https://coveralls.io/github/hammerlab/stancache?branch=master)
[![PyPI version](https://img.shields.io/pypi/v/stancache.svg)](https://pypi.python.org/pypi/stancache)

stancache
===============================

author: Jacqueline Buros Novik

Overview
--------

Filecache for stan models

Installation
--------------------

You can install this package from pypi using pip:

    $ pip install stancache

Or clone the repo & run setup.py:

    $ git clone https://github.com/hammerlab/stancache.git
    $ python setup.py install

Introduction
------------

This is a filecache for [pystan](https://pystan.readthedocs.io/en/latest/) models fit to data. Each pystan model fit to data is comprised of two parts - the compiled model code & the result of MCMC sampling of that model given data. Both model compilation & model sampling can be time-consuming operations, so both are cached as separate [pickled](https://docs.python.org/3/library/pickle.html) objects on the filesystem. 

This separation allows one to (for example) compile a model once & execute the model several times - caching the result each time. You might be testing the model on different samples of data, or using different initializations or passing in different parameters.

Loading pickled pystan.fit objects into memory is also safer using `cached_stan_fit()` since this will ensure that the compiled model is first unpickled before the fit model.

Getting started
---------------

### Configuratation

The configuration uses python's [configparser](https://docs.python.org/2/library/configparser.html) module, allowing the user to either load a `config.ini` file from disk or set the configuration in code.

`stancache` looks for a default config file to be located in `'~/.stancache.ini'`. You can modify this using `stancache.config.load_config('/another/config/file.ini')`. 

Currently, the config settings include

* `CACHE_DIR` (defaults to `.cached_models`)
* `SEED` (seed value passed to `pystan.stan` for reproducible research)
* `SET_SEED` (boolean, whether to set the random.seed, systemwide in addition to stan_seed)

You can use `config.set_value(NAME=value)` to modify a setting.

For example, you might want to set up a shared-nfs-mount containing fitted models among your collaborators:

```python
from stancache import config
config.set_value(CACHE_DIR='/mnt/trial-analyses/cohort1/stancache')
```

An updated list of configuration defaults is available in [defaults.py](https://github.com/hammerlab/stancache/blob/master/stancache/defaults.py)

### Fitting cached models

Once you have configured your settings, you would then use `stancache.cached_stan_fit` to fit your model, like so:

```python
from stancache import stancache
fit1 = stancache.cached_stan_fit(file = '/path/to/model.stan', data=dict(), chains=4, iter=100)
```

The options to `cached_stan_fit` are the same as those to `pystan.stan` (see [pystan.stan documentation](https://pystan.readthedocs.io/en/latest/api.html#pystan.stan)).

Also see `?stancache.cached_stan_fit` for more details.

### Caching other items

The caching is very sensitive to certain things which would change the returned object, such as the sort order of your data elements within the dictionary. But is not sensitive to other things (such as whether you use a file-based stan code or string-based version of same code). 

In practice, we find that it can be helpful to cache data-preparation steps, especially when simulating data. There is thus as `stancache.cached()` wrapper function for this purpose, to cache all objects _other_ than `pystan.stan` objects using the same file-cache settings. 

A fairly common set-up for us is, for example, to fit a set of models in a distributed execution environment, then review the model results in a set of jupyter notebooks. In this case, in our jupyter notebook we will set a parameter of `cache_only=True` when loading model results into the Jupyter notebook to force a failure if the cache is not available. 

Contributing
------------

TBD

Examples
--------

For example (borrowing from [pystan's docs](https://pystan.readthedocs.io/en/latest/getting_started.html)):

```python
import stancache

schools_code = """
data {
    int<lower=0> J; // number of schools
    real y[J]; // estimated treatment effects
    real<lower=0> sigma[J]; // s.e. of effect estimates
}
parameters {
    real mu;
    real<lower=0> tau;
    real eta[J];
}
transformed parameters {
    real theta[J];
    for (j in 1:J)
    theta[j] <- mu + tau * eta[j];
}
model {
    eta ~ normal(0, 1);
    y ~ normal(theta, sigma);
}
"""

schools_dat = {'J': 8,
               'y': [28,  8, -3,  7, -1,  1, 18, 12],
               'sigma': [15, 10, 16, 11,  9, 11, 10, 18]}

# fit model to data
fit = stancache.cached_stan_fit(model_code=schools_code, data=schools_dat,
                                iter=1000, chains=4)

# load fit model from cache
fit2 = stancache.cached_stan_fit(model_code=schools_code, data=schools_dat,
                                 iter=1000, chains=4)
```

In addition, there are a number of publicly-accessible ipynbs using [stancache](http://github.com/hammerlab/stancache). 

These include:

* [survivalstan-examples](http://github.com/jburos/survivalstan-examples)
* [immune-infiltrate-explorations](http://github.com/hammerlab/immune-infiltrate-explorations)
    - e.g. [model-single-origin-samples/0.830 model3 by cell_type (n=500).ipynb](http://nbviewer.jupyter.org/github/hammerlab/immune-infiltrate-explorations/blob/master/model-single-origin-samples/0.830%20model3%20by%20cell_type%20%28n%3D500%29.ipynb)
    
If you know of other examples, please let us know and we will add them to this list.
