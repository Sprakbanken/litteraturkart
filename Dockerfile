FROM python:3.11
EXPOSE 8501
WORKDIR /app/

RUN mkdir -p /app/litteraturkart

RUN pip3 install --upgrade pip
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt

COPY litteraturkart/*.py ./litteraturkart/.

CMD streamlit run litteraturkart/app.py

