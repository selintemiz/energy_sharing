
from optimizer import Optimizer, OptimizerExt

import numpy as np
import pandas as pd
from prophet import Prophet
from datetime import datetime, timedelta

### Stub predictors only used for benchmarking ###

def average_predictor(table, t, i0=None, imax=None, nbdays=7):
    return sum(table[(t-24*i)%len(table)] for i in range(1,nbdays+1)) / nbdays

def previous_predictor(table, t, i0, imax, nbdays=7):
    return table[(t-1)%len(table)]

def mix_predictor(table, t, i0, imax, nbdays=7):
    base = table[(t-1)%len(table)] + (table[(t-1)%len(table)]-table[(t-2)%len(table)])
    if imax == i0:
        return base
    return base*(imax-t)/(imax-i0) + average_predictor(table, t) * (t-i0)/(imax-i0)

def mix2_predictor(table, t, i0, imax, nbdays=7):
    base = table[(t-1)%len(table)]
    if imax == i0:
        return base
    return base*(imax-t)/(imax-i0) + average_predictor(table, t) * (t-i0)/(imax-i0)

def linear_predictor(table, t, i0, imax, basis=average_predictor):
    if imax == i0:
        return table[t]
    else:
        return table[t]*(imax-t)/(imax-i0) + basis(table, t) * (t-i0)/(imax-i0)

### Prophet-based predictor ###

def hourly_series_to_prophet_format(in_data, t_start=0, start_date = datetime(2012, 1, 1)):
    return [[start_date+timedelta(hours=t_start+t),energy] for t, energy in enumerate(in_data)]

def hourly_series_to_prophet_df(data, t_start=0):
    return pd.DataFrame(hourly_series_to_prophet_format(data,t_start), columns=["ds", "y"])

def predict(df, forecast_window):
    m = Prophet(changepoint_prior_scale=0.05).fit(df)
    future = m.make_future_dataframe(periods=forecast_window, freq='h')
    fcst = m.predict(future)
    return [fcst.iloc[i, -1] for i in range(-forecast_window,0)]

def extend_optimizer_with_predicted_values(opt, h, start_hour=0, forecast_window = 48):
    #opt = opt.subset([h])

    df_cons = hourly_series_to_prophet_df(opt.cons[h],start_hour)
    df_sun = hourly_series_to_prophet_df(opt.sun[h],start_hour)
    df_price = hourly_series_to_prophet_df(opt.price,start_hour)

    # Requires new array allocation
    opt.cons[h] = np.append(opt.cons[h], predict(df_cons, forecast_window) )
    opt.sun[h] = np.append(opt.sun[h], predict(df_sun, forecast_window) )
    opt.price = np.append(opt.price, predict(df_price, forecast_window) )

    return opt
