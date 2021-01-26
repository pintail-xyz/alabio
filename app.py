# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd

from datetime import datetime
import time
import json
from uniprice import AssetRegister
from blocktimes import Blocktimes

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

ar = AssetRegister()
ar.add_all_assets()
d = ar.get_price_time_series()
symbols = [k for k in d if k != 'time']
dd_options = [{'label':sym, 'value':sym} for sym in ['ETH'] + symbols]

app.layout = html.Div(children=[
                html.H1(children="Ethereum token explorer"),
                html.Div(children="Uniswap-derived token price data"),
                html.Div(children=[
                    html.Div(style={'width':'49%', 'display':'inline-block'}, children=[
                        html.Label("Quote asset(s)"),
                        dcc.Dropdown(id='quote-dropdown', options=dd_options, value=['ETH'],
                                     multi=True)]),
                    html.Div(style={'width':'49%', 'display':'inline-block'}, children=[
                        html.Label("Base asset"),
                        dcc.Dropdown(id='base-dropdown', options=dd_options, value=symbols[0])])
                    ]),
                dcc.Graph(id='price-graph'),
                dcc.Store(id='store-raw', data=d),
                dcc.Store(id='store-processed')
            ])

app.clientside_callback(
    """
    function(data, base_symbol) {
      var n_rows = data['time'].length;
      var output = {};
      var quote_symbols = [];
      for (symbol in data) {
        if (![base_symbol, 'time'].includes(symbol)) { quote_symbols.push(symbol); }
      }
      if (base_symbol == 'ETH') {
        for (symbol of quote_symbols) {
          output[symbol] = {x: data['time'], y: data[symbol], mode: 'lines', name: symbol};
        }
      } else {
        output.ETH = {x: data['time'], y: [], mode: 'lines', name: 'ETH'};
        for (symbol of quote_symbols) {
          output[symbol] = {x: data['time'], y: [], mode: 'lines', name: symbol};
        }
        var i, base_price;
        for (i = 0; i < n_rows; i++) {
          base_price = data[base_symbol][i];
          output.ETH.y.push(1 / base_price);
          for (symbol of quote_symbols) {
           output[symbol].y.push(data[symbol][i] / base_price); 
          }
        }
      }
      for (symbol in output) {
        var start_index = 0;
        for (p of output[symbol].y) {
          if (p > 0 && Number.isFinite(p)) { break; }
          start_index++;
        }
        output[symbol].x = output[symbol].x.slice(start_index);
        output[symbol].y = output[symbol].y.slice(start_index);
      }
      return {data: output, unit: base_symbol};
    }
    """,
    Output('store-processed', 'data'),
    Input('store-raw','data'),
    Input('base-dropdown', 'value')
)

app.clientside_callback(
    """
    function(store_data, quote_symbols) {
      var data = store_data.data;
      var unit = store_data.unit;
      var output = [];
      for (symbol of quote_symbols) {
       if (symbol in data) {
         output.push(Object.assign({}, data[symbol]));
       }
      }
      var base_symbol = store_data.base_symbol;
      var y_label = "Price (" + unit + ")";
      var title = "Price of " + quote_symbols[0];
      if (quote_symbols.length > 1) {
        for (var i=1; i < quote_symbols.length; i++) {
          title += ', ' + quote_symbols[i];
        }
      }
      title += " measured in " + unit;

      layout = {title: title, yaxis: {title: y_label}}
      return {'data': output, 'layout': layout};
    }
    """,
    Output('price-graph', 'figure'),
    Input('store-processed', 'data'),
    Input('quote-dropdown', 'value')
)

if __name__ == '__main__':
        app.run_server(debug=True, port=8051, host='0.0.0.0')
