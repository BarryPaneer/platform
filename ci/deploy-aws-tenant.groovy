@NonCPS

def key_file = '/opt/password.txt'
def ec2_location = null

pipeline {
    agent { node { label 'master' } }
    environment {
        AWS_ACCESS_KEY_ID     = credentials('jenkins-aws-secret-key-id')
        AWS_SECRET_ACCESS_KEY = credentials('jenkins-aws-secret-access-key')
    }
    parameters {
        choice(name: 'REGION', choices: ['CN', 'FR', 'US', 'SG'], description: 'where to deploy APP')
        string(name: 'CLIENT', defaultValue: 'learning-customer', description: 'what instance name of client APP')
    }
    stages{
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
        stage('Setup region') {
            steps {
                script {
                    if (params.REGION == 'CN') {
                        ec2_location = 'ap-southeast-1'
                    } else if (params.REGION == 'FR') {
                        ec2_location = 'eu-west-1'
                    } else if (params.REGION == 'US') {
                        ec2_location = 'us-east-1'
                    } else if (params.REGION == 'SG') {
                        ec2_location = 'ap-southeast-1'
                    }
                }
            }
        }
        stage('Deploy EC2 instance') {
            steps {                
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venvec2/bin/activate
                    ansible-playbook -e "region=${ec2_location}" -e "client_name=${params.CLIENT}" --vault-password-file "${key_file}" lt_ec2_tenant.yml
                    """
                }
            }
        }
        stage('Check apt process') {
            steps {
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venvec2/bin/activate
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${params.CLIENT}_tenant" -u ubuntu -e 'ansible_python_interpreter=/usr/bin/python3' --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" lt_ec2_apt.yml
                    """
                }
            }
        }
        stage('Create DB on stateful instance') {
            steps {
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venv2/bin/activate
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${ec2_location}_stateful" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" -e '@/opt/repo/hawthorn_inventory/group_vars/${params.CLIENT}_tenant/passwords.yml' tenant_setup.yml
                    """
                }
            }
        }
        stage('Deploy tenant APP') {
            steps {
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venv2/bin/activate
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${params.CLIENT}_tenant" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" -e "sensu_subscription=hawthorn-app" -e "THEMES_GIT_PATH=edx" -e "client_name=${params.REGION}-${params.CLIENT}_tenant" -e "sentry_project=${params.REGION}-${params.CLIENT}" -e "apm_project=${params.REGION}-${params.CLIENT}" lt_edxapp_with_worker.yml
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${params.CLIENT}_tenant" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" -e "client_name=${params.CLIENT}" lt_ec2_tenant_after.yml
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${params.CLIENT}_tenant" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" lt_xqueue.yml
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${params.CLIENT}_tenant" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" lt_forum.yml
                    ansible-playbook -i /opt/repo/hawthorn_inventory/hosts.ini -l "${params.CLIENT}_tenant" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --skip-tags 'to-remove' lt_certs.yml
                    """
                }
            }
        }
    }
}