# start with qsmxt container
FROM vnmd/qsmxt_8.2.0

# install necessary software
RUN pip3 install flywheel-sdk

COPY run.py /flywheel/v0/run.py
RUN chmod +x /flywheel/v0/run.py
#ENTRYPOINT [ "/bin/bash" ]
ENTRYPOINT ["python3",  "/flywheel/v0/run.py"]
