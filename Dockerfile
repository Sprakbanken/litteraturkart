FROM python:3.11
EXPOSE 8501
WORKDIR /app/


RUN pip3 install --upgrade pip
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt

COPY *.py ./

CMD streamlit run app.py

