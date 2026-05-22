import guile as gui
import matplotlib.pyplot as plt

df = gui.state(None)
status_box = gui.state(None)

def get_ks_mesonet(station, start_date, end_date, variables, interval='day'):
    fmt = '%Y%m%d%H%M%S'
    start_date = pd.to_datetime(start_date).strftime(fmt)
    end_date = pd.to_datetime(end_date).strftime(fmt)
    variables = ','.join(variables)
    url = f"http://mesonet.k-state.edu/rest/stationdata/?stn={station}&int={interval}&t_start={start_date}&t_end={end_date}&vars={variables}"
    url = url.replace(" ", "%20")
    df = pd.read_csv(url, na_values='M')
    return df



@gui.app("Kansas Mesonet Data Explorer", width=800, height=400)
def gui():
    with gui.row():
        with gui.col():
            station = gui.select(label='Station', options=['Manhattan','Ashland Bottoms'])
            interval = gui.select(label='Interval', options=[('day','Daily'),('hourly','Hourly')])
            variables = gui.checkbox("TEMP2MAVG", value=False)
            start_date = gui.date_input("From", key="from")
            end_date = gui.date_input("To", key="to")

            run = gui.button("Request", on_click=get_ks_mesonet)

        with gui.col():
            if df is None:
                status_box.set('No data'))
            else:
                table = gui.table(df)



df = gui.state(None)   # None = nothing loaded

def load_file(path):
    df.set(pd.read_csv(path))   # triggers re-render

# ui() just asks one question:
if df.value is None:
    # show placeholder
else:
    gui.table(df.value.to_dict("records"))