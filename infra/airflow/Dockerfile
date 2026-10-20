FROM apache/airflow:3.3.1-python3.10

# Keep project dependencies separate from Airflow's own dependency constraints.
USER root
RUN mkdir -p /opt/retail-venv /workspace /opt/airflow/auth && chown -R airflow:root /opt/retail-venv /workspace /opt/airflow/auth
USER airflow
COPY requirements.txt /tmp/retail-requirements.txt
RUN python -m venv /opt/retail-venv && /opt/retail-venv/bin/pip install --no-cache-dir -r /tmp/retail-requirements.txt
ENV RETAIL_PYTHON=/opt/retail-venv/bin/python
ENV PYTHONPATH=/workspace
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /workspace
