@NonCPS

def key_file = '/opt/password.txt'

pipeline {
    agent { node { label 'master' } }
    environment {
        AWS_ACCESS_KEY_ID     = credentials('jenkins-aws-secret-key-id')
        AWS_SECRET_ACCESS_KEY = credentials('jenkins-aws-secret-access-key')
    }
    parameters {
        string(name: 'REGION', defaultValue: 'ap-southeast-1', description: 'where to deploy datacenter')
    }
    stages {
        stage('GIT configuration Repo') {
            steps {
                dir('configuration') {
                    git credentialsId: 'slidemoon', branch: 'master', url: 'https://github.com/Learningtribes/configuration.git'
                    sh """
                    virtualenv /tmp/.venv2
                    . /tmp/.venv2/bin/activate
                    make requirements
                    """
                }
            }
        }
        stage('Deploy EC2 instance') {
            steps {
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venvec2/bin/activate
                    ansible-playbook -e "region=${params.REGION}" --vault-password-file "${key_file}" lt_ec2_stateful.yml
                    """
                }
            }
        }
        stage('Check apt process') {
            steps {
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venvec2/bin/activate
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${params.REGION}_stateful" -u ubuntu -e 'ansible_python_interpreter=/usr/bin/python3' --private-key /opt/instanceskey/"${params.REGION}"_platform_key.pem --vault-password-file "${key_file}" lt_ec2_apt.yml
                    """
                }
            }
        }
        stage('Deploy stateful APP') {
            steps {
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venv2/bin/activate
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${params.REGION}_stateful" -u ubuntu --private-key /opt/instanceskey/"${params.REGION}"_platform_key.pem -e "sensu_subscription=hawthorn-db" -e "client_name=${params.REGION}_stateful" --vault-password-file "${key_file}" lt_stateful_center.yml
                    """
                }
            }
        }
    }
}