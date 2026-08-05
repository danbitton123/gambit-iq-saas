import pandas as pd

from data.repository import SQLContext, get_repository
from pages.data_import import render

repo=get_repository()
render(SQLContext(repo,pd.Timestamp("2026-05-07"),pd.Timestamp("2026-08-04"),"All markets"))
