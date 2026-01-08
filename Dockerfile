ARG PYTHON_VERSION=3.10-slim
ARG PYTHON_BUILD_VERSION=$PYTHON_VERSION-buster

FROM python:${PYTHON_BUILD_VERSION}

ARG USER_ID
ARG GROUP_ID

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN groupadd -g $GROUP_ID -o user && useradd -o -m -u $USER_ID -g user user

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends netcat && \
    apt-get clean

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /opt/src

COPY ./src .

EXPOSE 8000

USER user
