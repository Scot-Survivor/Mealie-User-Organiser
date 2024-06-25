FROM python:3.9-alpine3.19
LABEL authors="Scot_Survivor"

ENV PYTHONUNBUFFERED=1

ADD main.py .
ADD requirements.txt .
# ADD email_templates ./email_templates

RUN pip3 install -r requirements.txt
RUN pip3 cache purge

CMD ["python3", "main.py"]