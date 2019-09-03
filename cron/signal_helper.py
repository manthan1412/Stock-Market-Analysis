import numpy as np
import pandas as pd

# Exponential moving average calculation
def EMA(df, col, win):
    ema = pd.DataFrame(columns=['%s EMA' % win])
    ema['%s EMA' % win] = pd.Series.ewm(df[col], span=win).mean()
    return ema


# Simple moving average calculation
def SMA(df, col, win):
    sma = pd.DataFrame(columns=['%s SMA' % win], index=np.arange(len(df[col])))
    sma['%s SMA' % win] = df[col].rolling(window=win).mean()
    return sma


def get_ages(sig):
    # Function to get indices of where the array changed values
    ages = np.where(np.roll(1*sig, 1) != 1*sig)[0] - 1
    return ages


# RSI calculation
def RSI(df, win):
    rsi = pd.DataFrame(columns=['RSI(%s)' % win], index=np.arange(len(df)))
    delta = df['Close'].diff().dropna()
    u = delta * 0
    d = u.copy()
    u[delta > 0] = delta[delta > 0]
    d[delta < 0] = -delta[delta < 0]
    u[u.index[win - 1]] = np.mean(u[:win])  # first value is sum of avg gains
    u = u.drop(u.index[:(win - 1)])
    d[d.index[win - 1]] = np.mean(d[:win])  # first value is sum of avg losses
    d = d.drop(d.index[:(win - 1)])
    rs = u.ewm(com=win - 1, adjust=False).mean() / \
         d.ewm(com=win - 1, adjust=False).mean()
    rsi['RSI(%s)' % win] = 100 - 100 / (1 + rs)
    return rsi


# Indicators used for bungees
# Stochastic indicator calculation
def STOCH(df, a, b):
    stoch = pd.DataFrame(columns=['Stoch(%s,%s)' % (a, b)])
    stoch['Stoch(%s,%s)' % (a, b)] = (((100 * (df['Close'] - df['Low'].rolling(window=a).min())
                         / (df['High'].rolling(window=a).max()
                           - df['Low'].rolling(window=a).min()))
                    .rolling(window=b).mean()))
    return stoch


# William's Percent R calculation
def WILLSR(df, win):
    willsr = pd.DataFrame(columns=['Wills Percent R(%s)' % win])
    hh = df['High'].rolling(window=win).max()
    ll = df['Low'].rolling(window=win).min()
    willsr['Wills Percent R(%s)' % win] = 100 - 100*((hh - df['Close'])/(hh - ll))
    return willsr


def main_signal(df):
    if len(df) < 34:
        return -1, -1

    # Return: curr_sig = 0 for Green, curr_sig = 1 for Yellow, curr_sig = 2 for Red
    # df = pandas.DataFrame({'Open': C[:, 0], 'High': C[:, 1], 'Low': C[:, 2], 'Close': C[:, 3]})
    # df = df.head(819)
    # Define EMA bands
    ema34_o = EMA(df, 'Open', 34).iloc[:].values
    ema34_h = EMA(df, 'High', 34).iloc[:].values
    ema34_l = EMA(df, 'Low',  34).iloc[:].values
    ema144 = EMA(df, 'Close', 144).iloc[:].values
    ema169 = EMA(df, 'Close', 169).iloc[:].values

    # Signals logic
    # Green signal
    green_sig = (ema34_o > ema144) & (ema34_h > ema144) & (ema34_l > ema144) \
              & (ema34_o > ema169) & (ema34_h > ema169) & (ema34_l > ema169)

    # Red signal
    red_sig = (ema34_o < ema144) & (ema34_h < ema144) & (ema34_l < ema144) \
            & (ema34_o < ema169) & (ema34_h < ema169) & (ema34_l < ema169)

    # Yellow signal
    max_values = np.amax([ema34_o, ema34_h, ema34_l], axis=0)
    min_values = np.amin([ema34_o, ema34_h, ema34_l], axis=0)
    yellow_sig = (ema144 > min_values) & (ema144 < max_values) \
               & (ema169 > min_values) & (ema169 < max_values)

    # Indices of where each signal is true
    idx = [(np.transpose(np.nonzero(green_sig)))[:, 0],
           (np.transpose(np.nonzero(yellow_sig)))[:, 0],
           (np.transpose(np.nonzero(red_sig)))[:, 0]]

    sig = [green_sig, yellow_sig, red_sig]

    last_index_list = []
    # Add signals with try/except block in case the signal has never triggered
    for row in idx:
        try:
            last_index_list.append(row[-1])
        except IndexError:
            last_index_list.append(0)

    # Find the most recent signal and its age
    curr_sig = np.argmax(last_index_list)
    sig_age = get_ages(sig[curr_sig])[-1]

    return curr_sig, green_sig.shape[0] - sig_age


def second_signal(df):
    if len(df) < 34:
        return -1

    # Define EMA bands
    ema34_o = EMA(df, 'Open', 34).iloc[:].values
    ema34_h = EMA(df, 'High', 34).iloc[:].values
    ema34_l = EMA(df, 'Low', 34).iloc[:].values
    ema12 = EMA(df, 'Close', 12).iloc[:].values
    close = df['Close'].iloc[:].values

    ema_max = np.maximum.reduce([ema34_o, ema34_h, ema34_l])
    ema_min = np.minimum.reduce([ema34_o, ema34_h, ema34_l])

    # Secondary signal logic:
    # Green signal: Close above the wave
    # Light signal: Close below the wave, but above the three magenta bands
    # Yellow signal: Close below the max of the magenta bands but above the min of them
    # Red signal: Close below all of the magenta bands

    # Signals logic
    # Green signal
    green_sig = close[-1] > ema12[-1]

    # Light signal
    light_sig = (close[-1] < ema12[-1]) & (close[-1] > ema_max[-1])

    # Yellow signal
    yellow_sig = (close[-1] < ema_max[-1]) & (close[-1] > ema_min[-1])

    # Red signal
    red_sig = close[-1] < ema_min[-1]

    sig = [green_sig, light_sig, yellow_sig, red_sig]
    return [i for i, x in enumerate(sig) if x][0]


def sma_cross(df):
    if len(df) < 30:
        return -1, -1

    # Return: curr_sig = 0 for Green, curr_sig = 1 for Red
    sma13 = SMA(df, 'Close', 13).fillna(value=0).iloc[:].values  # .iloc[:, 0]
    sma30 = SMA(df, 'Close', 30).fillna(value=0).iloc[:].values

    # Signals logic
    green_sig = (sma13 > sma30)

    # Red signal
    red_sig = (sma30 > sma13)

    # Indices of where each signal is true
    idx = [(np.transpose(np.nonzero(green_sig)))[:, 0],
           (np.transpose(np.nonzero(red_sig)))[:, 0]]

    sig = [green_sig, red_sig]

    last_index_list = []
    # Add signals with try/except block in case the signal has never triggered
    for row in idx:
        try:
            last_index_list.append(row[-1])
        except IndexError:
            last_index_list.append(0)

    # Find the most recent signal and its age
    curr_sig = np.argmax(last_index_list)
    sig_age = get_ages(sig[curr_sig])[-1]

    return curr_sig, green_sig.shape[0] - sig_age


def rsi_threshold(df):
    if len(df) < 9:
        return -1, -1

    # Return 0 if the RSI is between 20 and 80, 1 if it's below 20, or 2 if it's above 80.
    rsi9 = RSI(df, 9).fillna(value=0).iloc[:].values

    # Incorporate the awesome oscillator - >0 for green, <0 for red
    # Gold, green, blue, red
    green_sig = rsi9 >= 80
    red_sig = rsi9 <= 20
    neutral_sig = (rsi9 < 80) & (rsi9 > 20)
    # Indices of where each signal is true
    idx = [(np.transpose(np.nonzero(neutral_sig)))[:, 0],
           (np.transpose(np.nonzero(green_sig)))[:, 0],
           (np.transpose(np.nonzero(red_sig)))[:, 0]]

    sig = [neutral_sig, green_sig, red_sig]

    last_index_list = []
    # Add signals with try/except block in case the signal has never triggered
    for row in idx:
        try:
            last_index_list.append(row[-1])
        except IndexError:
            last_index_list.append(0)

    # Find the most recent signal and its age
    curr_sig = np.argmax(last_index_list)
    sig_age = get_ages(sig[curr_sig])[-1]

    return curr_sig, green_sig.shape[0] - sig_age


def bungee_values(df):
    # Return the current values of each of the four main bungees
    # Return, in order: yellow, green, blue, red
    if len(df) < 82:
        return 0, 0, 0, 0

    bg_y = STOCH(df, 76, 4).iloc[:, 0]
    bg_g = STOCH(df, 34, 3).iloc[:, 0]
    bg_u = STOCH(df, 16, 3).iloc[:, 0]
    bg_r = STOCH(df, 8, 3).iloc[:, 0]

    return int(bg_y.iloc[-1]), int(bg_g.iloc[-1]), int(bg_u.iloc[-1]), int(bg_r.iloc[-1])


def royal_signal(df):
    if len(df) < 82:
        return -1, -1

    """
    Return a number that corresponds to which royal signal is the most recent, and its age.
    0: BullishNoble,
    1: BearishNoble,
    2: BullishRoyal,
    3: BearishRoyal,
    """

    bg_y = STOCH(df, 76, 4).fillna(0).iloc[:].values
    bg_g = STOCH(df, 34, 4).fillna(0).iloc[:].values
    bg_u = STOCH(df, 16, 4).fillna(0).iloc[:].values
    bg_r = STOCH(df, 8, 4).fillna(0).iloc[:].values

    bullishRoyal = (bg_r < 20) & (bg_u < 20) & (bg_y < 20) & (bg_g < 20)
    bearishRoyal = (bg_r > 80) & (bg_u > 80) & (bg_y > 80) & (bg_g > 80)
    bullishNoble = (bg_y > 50) & (bg_g < 20)
    bearishNoble = (bg_y < 50) & (bg_g > 80)

    # Indices of where each signal is true
    idx = [(np.transpose(np.nonzero(bullishNoble)))[:, 0],
           (np.transpose(np.nonzero(bearishNoble)))[:, 0],
           (np.transpose(np.nonzero(bullishRoyal)))[:, 0],
           (np.transpose(np.nonzero(bearishRoyal)))[:, 0]]

    sig = [bullishNoble, bearishNoble, bullishRoyal, bearishRoyal]

    last_index_list = []
    # Add signals with try/except block in case the signal has never triggered
    for row in idx:
        try:
            last_index_list.append(row[-1])
        except IndexError:
            last_index_list.append(0)

    # Find the most recent signal and its age
    curr_sig = np.argmax(last_index_list)
    sig_age = get_ages(sig[curr_sig])[-1]

    return curr_sig, bullishRoyal.shape[0] - sig_age


# return candlestick shapes
def candlestick_shapes(df):
    if len(df) < 4:
        return -1, -1

    """
    Return a number that corresponds to which candle shape is the most recent, and its age.
    0: Doji,                colour: grey
    1: Evening Star,        colour: red
    2: Morning Star,        colour: green
    3: Hammer,              colour: green
    4: Inverted Hammer,     colour: green
    5: Bearish Engulfing,   colour: green
    6: Bullish Engulfing,   colour: red
    7: Hanging Man,         colour: red
    8: Dark Cloud Cover,    colour: red
    """
    # np.where(<boolean logic>)[0] # gives you indices where array is true
    # array[-1] in pinescript: access the previous value

    # For easy conversion from pinescript to python
    open = df['Open']
    close = df['Close']
    high = df['High']
    low = df['Low']
    open1 = df['Open'].shift(periods=1).fillna(value=0)
    high1 = df['High'].shift(periods=1).fillna(value=0)
    close1 = df['Close'].shift(periods=1).fillna(value=0)
    open2 = df['Open'].shift(periods=2).fillna(value=0)
    high2 = df['High'].shift(periods=2).fillna(value=0)
    close2 = df['Close'].shift(periods=2).fillna(value=0)

    # Element wise min/max between two dataframes in pandas
    pmin = lambda a, b: pd.concat([a, b], axis=1).min(axis=1)
    pmax = lambda a, b: pd.concat([a, b], axis=1).max(axis=1)

    # Doji: (abs(open - close) <= (high - low) * DojiSize), DojiSize = 0.05
    doji = (abs(open - close) <= (high - low) * 0.05)

    # Evening star = (close[2] > open[2] and min(open[1], close[1]) > close[2] and open < min(open[1], close[1]) and close < open)
    eveningStar = ((close2 > open2)
                   & (pmin(open1, close1) > close2)
                   & (open < pmin(open1, close1))
                   & (close < open))

    # Morning star: (close[2] < open[2] and max(open[1], close[1]) < close[2] and open > max(open[1], close[1]) and close > open)
    morningStar = ((close2 < open2)
                   & (pmax(open1, close1) < close2)
                   & (open > pmax(open1, close1))
                   & (close > open))

    # Hammer: (((high - low)>3*(open -close)) and  ((close - low)/(.001 + high - low) > 0.6) and ((open - low)/(.001 + high - low) > 0.6))
    hammer = (((high - low) > 3 * (open - close))
              & ((close - low) / (0.001 + high - low) > 0.6)
              & ((open - low) / (0.001 + high - low) > 0.6))

    # Inv. hammer: (((high - low)>3*(open -close)) and  ((high - close)/(.001 + high - low) > 0.6) and ((high - open)/(.001 + high - low) > 0.6))
    invertedHammer = ((((high - low) > 3 * (open - close))
                       & ((high - close) / (.001 + high - low) > 0.6)
                       & ((high - open) / (.001 + high - low) > 0.6)))

    # Bearish engulfing: (close[1] > open[1] and open > close and open >= close[1] and open[1] >= close and open - close > close[1] - open[1] )
    bearishEngulfing = ((close1 > open1)
                        & (open > close)
                        & (open >= close1)
                        & (open1 >= close)
                        & ((open - close) > close1 - open1))

    # Bullish engulfing: (open[1] > close[1] and close > open and close >= open[1] and close[1] >= open and close - open > open[1] - close[1] )
    bullishEngulfing = ((open1 > close1)
                        & (close > open)
                        & (close >= open1)
                        & (close1 >= open)
                        & ((close - open) > (open1 - close1)))

    # Hanging man: (((high-low>4*(open-close))and((close-low)/(.001+high-low)>=0.75)and((open-low)/(.001+high-low)>=0.75)) and high[1] < open and high[2] < open)
    hangingMan = (((high - low) > (4 * (open - close)))
                    & ((close - low) / ((.001 + high - low) >= 0.75))
                    & ((open - low) / (.001 + high - low) >= 0.75)
                    & (high1 < open)
                    & (high2 < open))

    # Dark cloud cover: ((close[1]>open[1])and(((close[1]+open[1])/2)>close)and(open>close)and(open>close[1])and(close>open[1])and((open-close)/(.001+(high-low))>0.6))
    darkCloudCover = (((close1 > open1)
                       & (((close1 + open1) / 2) > close)
                       & (open > close)
                       & (open > close1)
                       & (close > open1)
                       & (((open - close) / (.001 + (high - low))) > 0.6)))

    idx = [(np.transpose(np.nonzero(doji)))[:, 0],
           (np.transpose(np.nonzero(eveningStar)))[:, 0],
           (np.transpose(np.nonzero(morningStar)))[:, 0],
           (np.transpose(np.nonzero(hammer)))[:, 0],
           (np.transpose(np.nonzero(invertedHammer)))[:, 0],
           (np.transpose(np.nonzero(bearishEngulfing)))[:, 0],
           (np.transpose(np.nonzero(bullishEngulfing)))[:, 0],
           (np.transpose(np.nonzero(hangingMan)))[:, 0],
           (np.transpose(np.nonzero(darkCloudCover)))[:, 0]]

    last_index_list = []
    # Add signals with try/except block in case the signal has never triggered
    for row in idx:
        try:
            last_index_list.append(row[-1])
        except IndexError:
            last_index_list.append(0)

    # Find the most recent signal and its age
    curr_sig = np.argmax(last_index_list)
    return curr_sig, len(df) - 1 - idx[curr_sig][-1]


# Main function
if __name__ == '__main__':
    # Read CSV
    df = pd.read_csv("./AMD_15min.csv").head(600)
    df.columns = ['Date', 'Open', 'High', 'Low', 'Close']

    # Reverse the order of the dataframe - comment this out if it flips your chart
    df = df[::-1]
    df.index = df.index[::-1]

    # Trim off the unnecessary bit of the minute timeframe data - can be unnecessary
    # depending on where you source your data
    if '-04:00' in df['Date'][0]:
        df['Date'] = df['Date'].str.slice(0, -6)

    # Convert the dates column to datetime objects
    df["Date"] = pd.to_datetime(df["Date"], format='%Y-%m-%d %H:%M:%S')

    names = ["Doji",
             "Evening Star",
             "Morning Star",
             "Hammer",
             "Inverted Hammer",
             "Bearish Engulfing",
             "Bullish Engulfing",
             "Hanging Man",
             "Dark Cloud Cover"]

    signal_names = ["BullishNoble",
                    "BearishNoble",
                    "BullishRoyal",
                    "BearishRoyal"]

    print("Main signal: " + str(main_signal(df)))
    print("Second signal: " + str(second_signal(df)))
    print("SMA cross signal: " + str(sma_cross(df)))
    print("RSI threshold: " + str(rsi_threshold(df)))
    print("Bungee values: " + str(bungee_values(df)))
    print("Candlestick shape: " + str(candlestick_shapes(df)) + ", " + names[candlestick_shapes(df)[0]])
    print("Royal signal: " + str(royal_signal(df)) + ", " + signal_names[royal_signal(df)[0]])

