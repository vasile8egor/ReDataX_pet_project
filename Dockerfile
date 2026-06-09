FROM apache/airflow:2.10.5

ENV PYTHONPATH /opt/airflow:/opt/airflow/dags:/opt/airflow/constants

USER airflow

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
