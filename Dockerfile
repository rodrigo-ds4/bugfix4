# Pre-built Docker image that already includes dependencies.
FROM swesmith.x86_64.adrienverge__yamllint.8513d9b9

# Setup working directory 
RUN mkdir -p /app
COPY . /app
WORKDIR /app

# Set up Conda shell integration
SHELL ["/bin/bash", "-c"]
# Set up automatic activation of the 'testbed' Conda environment
# This appends the activation command to ~/.bashrc for interactive shells
RUN echo "source /opt/miniconda3/etc/profile.d/conda.sh && conda activate testbed" >> ~/.bashrc
ENV PATH=/opt/miniconda3/envs/testbed/bin:$PATH
ENV CONDA_DEFAULT_ENV=testbed

# Optional: Enter the testcase you wanted to execute here or directly use run command to specify the test cases to run
# Ex: CMD ["pytest", "tests/test_example.py"]
    