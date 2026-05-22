import guile as gui
import matplotlib.pyplot as plt

df = gui.state(None)
status_box = gui.state(None)

def get_ks_mesonet(station, variables, interval):
    variables = ','.join(variables)
    date_start = '20260401000000'
    date_end = '20260501000000'
    #date_str = date.strftime('%Y%m%d%H%M%S')
    url = f"http://mesonet.k-state.edu/rest/stationdata/?stn=all&int={interval}&t_start={date_start}&t_end={date_end}&vars={variables_str}"
    url = url.replace(" ", "%20")

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            df_request = pd.read_csv(url, na_values='M')
            df.set(df_request) 

            break
        except Exception as e:
            status_box.set(f"Attempt {attempt + 1}/{max_attempts} failed for {date_str}: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2)
            else:
                raise RuntimeError(f"Mesonet request failed after {max_attempts} attempts for {date_str}") from e
    return df_request



@gui.app("Kansas Mesonet Data Explorer", width=800, height=400)
def gui():
    with gui.row():
        with gui.col():
            station = gui.select(label='Station', options=['Manhattan','Ashland Bottoms'])
            interval = gui.select(label='Interval', options=[('day','Daily'),('hourly','Hourly')])
            variables = gui.checkbox("TEMP2MAVG", value=False)
            run = gui.button("Request", onclick=get_ks_mesonet)

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