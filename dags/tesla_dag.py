from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import BranchPythonOperator, PythonOperator
from airflow.operators.postgres_operator import PostgresOperator
from airflow.hooks.postgres_hook import PostgresHook

from datetime import datetime, timedelta
import pandas as pd
import os

def store_data():
    hook = PostgresHook(postgres_conn_id='postgres')
    hook.copy_expert(sql='''
        COPY stocks.tesla(date, close) 
        FROM STDIN DELIMITER ','
        CSV HEADER 
        ''', filename='/tmp/tesla_processed.csv')

def processing_data():
    data = pd.read_csv('/tmp/tesla_stock_prices.csv')
    data.to_csv('/tmp/tesla_processed.csv', columns=['Date','Close'], index=False)

def is_data_empty():
    filesize = os.path.getsize('/tmp/tesla_stock_prices.csv')
    if filesize <= 0:
        return 'alerting_data'
    return 'processing_data'

default_args = {
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

with DAG('tesla_dag', 
    description="Adams test DAG", 
    start_date=datetime(2020,1,1), 
    schedule_interval="*/10 * * * *", 
    catchup=False) as dag:

        downloading_data = BashOperator(
            task_id='downloading_data',
            bash_command='curl https://raw.githubusercontent.com/marclamberti/training_materials/master/data/tesla_stock_prices.csv --output /tmp/tesla_stock_prices.csv'
        )

        checking_data = BranchPythonOperator(
            task_id='checking_data',
            python_callable=is_data_empty
        )

        alerting_data = BashOperator(
            task_id='alerting_data',
            bash_command='echo "Dataset is empty"'
        )

        processing_data = PythonOperator(
            task_id='processing_data',
            python_callable=processing_data
        )

        creating_table = PostgresOperator(
            task_id='creating_table',
            postgres_conn_id='postgres',
            sql='sql/CREATE_TABLE_STOCKS.sql'
        )

        storing_data = PythonOperator(
            task_id='storing_data',
            python_callable=store_data
        )

        downloading_data >> checking_data >> [ alerting_data, processing_data ]
        processing_data >> creating_table >> storing_data

