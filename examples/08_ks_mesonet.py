# Import guile library
import guile as gui

# Import science libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# Custom function
def get_ks_mesonet(station, start_date, end_date, variables, interval='day'):
    """Function that requests weather data from the Kansas Mesonet."""
    print(variables)
    fmt = '%Y%m%d%H%M%S'
    start_date = pd.to_datetime(start_date).strftime(fmt)
    end_date = pd.to_datetime(end_date).strftime(fmt)
    variables = ','.join(variables)
    url = f"http://mesonet.k-state.edu/rest/stationdata/?stn={station}&int={interval}&t_start={start_date}&t_end={end_date}&vars={variables}"
    url = url.replace(" ", "%20")
    df = pd.read_csv(url, na_values='M')
    return df


# State
data = gui.state(None)
station = gui.state('Manhattan')
start_date = gui.state('2026-01-01')
end_date = gui.state('2026-05-01')
variables = gui.state(['TEMP2MAVG'])
interval = gui.state('day')


# Callback
def run():
    df = get_ks_mesonet(station.value,start_date.value,end_date.value,variables.value,interval.value)
    data.set(df)

def save(path):
    if path and data.value is not None:
        data.value.to_csv(path, index=False)
        
# Layout
@gui.app("Kansas Mesonet Data", width=600, height=400)
def ui():
    gui.title("Kansas Mesonet Data Download")
    with gui.row(gap=5):
        with gui.col(padding=20):
            gui.select(label='Station', options=['Manhattan','Ashland Bottoms'], on_change=station.set, key='station')
            gui.date_input("Start date", value=start_date, on_change=start_date.set, key="from")
            gui.date_input("End date", value=end_date, on_change=end_date.set, key="to")
            gui.multiselect(["TEMP2MAVG","SR","PRECIP"], value=variables, on_change=variables.set, key='variables')
            gui.select(label='Interval', options=[('day','Daily'),('hourly','Hourly')], value=interval, on_change=interval.set, key='interval')
            gui.button("Request", on_click=run)

        with gui.col(padding=20):
            if data.value is None:
                gui.text('No data yet')
            else:
                gui.file_picker("Save CSV", save=True, file_types=("CSV Files (*.csv)",), on_change=save,  disabled=data.value is None, key="save")
                with gui.scroll(max_height=300):
                    gui.table(data.value)




