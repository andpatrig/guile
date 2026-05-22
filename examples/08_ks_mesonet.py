# Import guile library
import guile as gui

# Import science libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# Custom function
def get_ks_mesonet(station, start_date, end_date, variables, interval='day'):
    """Function that requests weather data from the Kansas Mesonet."""
    fmt = '%Y%m%d%H%M%S'
    start_date = pd.to_datetime(start_date).strftime(fmt)
    end_date = pd.to_datetime(end_date).strftime(fmt)
    variables = ','.join(variables)
    url = f"http://mesonet.k-state.edu/rest/stationdata/?stn={station}&int={interval}&t_start={start_date}&t_end={end_date}&vars={variables}"
    url = url.replace(" ", "%20")
    df = pd.read_csv(url, na_values='M')
    return df

# guile state variables
data = gui.state(None)

def run():
    data.set(get_ks_mesonet(station,start_date,end_date,variables,interval))

# guile layout
@gui.app("Kansas Mesonet Data Explorer", width=800, height=400)
def ui():
    with gui.row():
        with gui.col():
            station = gui.select(label='Station', options=['Manhattan','Ashland Bottoms'])
            start_date = gui.date_input("From", key="from")
            end_date = gui.date_input("To", key="to")
            variables = gui.multiselect(["TEMP2MAVG","SRAVG"])
            interval = gui.select(label='Interval', options=[('day','Daily'),('hourly','Hourly')])
            gui.button("Request", on_click=run)

        with gui.col():
            if data.value is None:
                gui.text('No data yet')
            else:
                table = gui.table(data.value)
