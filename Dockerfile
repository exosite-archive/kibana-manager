FROM gliderlabs/alpine:3.4

MAINTAINER Alex Wauck "alexwauck@exosite.com"

RUN apk --no-cache add --update python python-dev py-pip build-base

RUN mkdir /etc/kibana-manager
COPY requirements.txt /etc/kibana-manager/requirements.txt
RUN pip install -r /etc/kibana-manager/requirements.txt
RUN rm /etc/kibana-manager/requirements.txt

COPY kibanamanager.py /usr/bin/kibanamanager
RUN chmod 0755 /usr/bin/kibanamanager

CMD ["/usr/bin/kibanamanager"]
