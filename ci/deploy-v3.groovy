@NonCPS
def commitHashForBuild(build) {
  def scmAction = build?.actions.find { action -> action instanceof jenkins.scm.api.SCMRevisionAction }
  return scmAction?.revision?.hash
}
def commitId = null
def upstreamProjectName = "edxapp.test"
def selectedIpAddress = null
def step = null
def failPercentage = null
def tags = null
def themes = null
def vars = "LT_KEY_FILE=/root/.ssh/id_rsa "
def machine = null


def platform_process = false
def theme_process = false
def theme_compile_process = false
def theme_deploy_process = false
def platform_with_theme_process = false
def translation_theme_process = false
def certs_process = false
def stage_certs_process = false
def restart_service_process = false
def xblock_process = false
def config_file_process = false
def proceed = true
def manual = true
def stage_auto_proceed = false
def stage_xblock_process = false
def this_environment = ''
def this_process = ''
def this_platform_branch = ''
def sub_theme_process = ''
def sub_restart_service_process = ''
def key_file = '/opt/password.txt'
def ec2_location = null
def instance_ip = ""
def compile_theme = []
def xblock_name = ''
def xblock_branch_name = ''
def tag_theme = ''
def tag_restart_service = ''
def tag_config_file = ''
def commit_id = ''
def lt_user_id = ''
def stage_deploy_branch_name = ''
def revert_process = false


def choose_environment(this_environment) {
    if (this_environment == 'PROD') {
        this_process = input message: "which process to run", parameters: [choice(name: 'process', choices: ['platform', 'theme', 'restart service', 'xblock', 'certs', 'config file', 'revert platform code'], description: 'which process to run')]
    } else if (this_environment == 'STAGING') {
        this_process = input message: "which process to run", parameters: [choice(name: 'process', choices: ['platform', 'theme', 'platform&theme', 'restart service', 'xblock', 'certs', 'config file'], description: 'which process to run')]
    } else if (this_environment == 'PREPROD') {
        this_process = input message: "which process to run", parameters: [choice(name: 'process', choices: ['platform', 'theme', 'restart service', 'xblock', 'certs', 'config file'], description: 'which process to run')]
    }
    return this_process
}

def choose_region() {
    ec2_region = input message: "which region to deploy", parameters: [choice(name: 'region', choices: ['FR', 'US', 'AZURE'],description: 'which region to deploy')]
    if (ec2_region == 'AZURE') {
        ec2_location = 'azure'
    } else if (ec2_region == 'FR') {
        ec2_location = 'eu-west-1'
    } else if (ec2_region == 'US') {
        ec2_location = 'us-east-1'
    }
    return ec2_location
}

def choose_tenant() {    
    if (ec2_location == 'azure') {
        def azure_list_parameters = []
        def azure_list_tenant = []
        azure_tenantout = sh script: "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_edxapp/files/get_azure_tenant_file.py ${env.WORKSPACE}/inventory/hosts.ini ${ec2_location}", returnStdout: true
        println azure_tenantout
        for (item in azure_tenantout.split('\n')) {
            def azure_sub_item_list = []
            for (i in item.split(',')) {
                azure_sub_item_list.add(i)
            }
            azure_list_tenant.add(azure_sub_item_list) 
        }
        println azure_list_tenant
        println '##############'
        for (item in azure_list_tenant) {
            def parameter_boolean = [$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: item[0]]
            azure_list_parameters.add(parameter_boolean)
        }
        azure_list_parameters.add([$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: 'ALL'])
        return [azure_list_parameters, azure_list_tenant]
        chooseOptions = input(id: 'chooseOptions', message: 'Select tenant options', parameters: azure_list_parameters)
        for (item in chooseOptions) {
            if (item.key == 'ALL' && item.value == true) {
                instance_ip = ''
                for (i in azure_list_tenant) {
                    for (int j = 1; j < i.size(); j++) {
                        instance_ip += i[j]
                        instance_ip += ','
                    }
                }
                break
            }
            if (item.value == true) {
                for (i in azure_list_tenant) {
                    if (i[0] == item.key) {
                        for (int j = 1; j < i.size(); j++) {
                        instance_ip += i[j]
                        instance_ip += ','
                        }
                    }
                }
            }
        }
    } else {
        sh "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_edxapp/files/check_tenant_file.py ${env.WORKSPACE}/inventory ${ec2_location} ${env.WORKSPACE}/configuration/playbooks/roles/lt_edxapp/files/credential-helper.sh"
        def list_parameters = []
        def list_tenant = []
        tenantout = sh script: "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_edxapp/files/get_tenant_list.py ${env.WORKSPACE}/inventory/hosts.ini ${ec2_location}", returnStdout: true
        println tenantout
        for (item in tenantout.split('\n')) {
            def sub_item_list = []
            for (i in item.split(',')) {
                sub_item_list.add(i)
            }
            list_tenant.add(sub_item_list)
        }
        println list_tenant
        println '##############'
        for (item in list_tenant) {
            println item
            def parameter_boolean = [$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: item[0]]
            list_parameters.add(parameter_boolean)
        }
        list_parameters.add([$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: 'ALL'])
        return [list_parameters, list_tenant]
        chooseOptions = input(id: 'chooseOptions', message: 'Select tenant options', parameters: list_parameters)
        for (item in chooseOptions) {
            if (item.key == 'ALL' && item.value == true) {
                instance_ip = ''
                for (i in list_tenant) {
                    for (int j = 1; j < i.size(); j++) {
                        instance_ip += i[j]
                        instance_ip += ','
                    }
                }
                break
            }
            if (item.value == true) {
                for (i in list_tenant) {
                    if (i[0] == item.key) {
                        for (int j = 1; j < i.size(); j++) {
                        instance_ip += i[j]
                        instance_ip += ','
                        }
                    }
                }
            }
        }
    }
}

def send_slack_message(stage_deploy_branch_name, step){
    if (step == 'start') {
        sh """
        curl -X POST -H 'Content-type: application/json' --data '{"text":"${stage_deploy_branch_name} is deploying on Stage"}' "${SLACK_WEBHOOK}"
        """   
    } else if (step == 'success_end') {
        sh """
        curl -X POST -H 'Content-type: application/json' --data '{"text":"${stage_deploy_branch_name} is successful to deploy on Stage"}' "${SLACK_WEBHOOK}"
        """
    } else if (step == 'failure_end') {
        sh """
        curl -X POST -H 'Content-type: application/json' --data '{"text":"${stage_deploy_branch_name} is failed to deploy on Stage"}' "${SLACK_WEBHOOK}"
        """
    }
}



pipeline {
    agent { node { label 'master' } }
    options {
        timestamps()
    }
    parameters { 
        string(name: 'DEPLOY_OWNER', defaultValue: '', description: 'Logging action')
    }
    environment {
        AWS_ACCESS_KEY_ID     = credentials('jenkins-aws-secret-key-id')
        AWS_SECRET_ACCESS_KEY = credentials('jenkins-aws-secret-access-key')
        GITHUB_USERNAME       = credentials('jenkins-github-username')
        GITHUB_PASSWORD       = credentials('jenkins-github-password')
        SLACK_WEBHOOK         = credentials('slack-webhook-on-channel-triboo-staging-token')
    }
    stages {
        stage('GIT configuration Repo') {
            steps {
                dir('configuration') {
                    git credentialsId: 'slidemoon', branch: 'master', url: 'https://github.com/Learningtribes/configuration.git'
                }
            }
        }
        stage('GIT inventory Repo') {
            steps {
                dir('inventory') {
                    git credentialsId: 'slidemoon', branch: 'master', url: 'https://github.com/Learningtribes/hawthorn_inventory.git'
                }
            }
        }
        stage('Get build user') {
            steps {
                script {
                    wrap([$class: 'BuildUser']) {
                            lt_user_id = env.BUILD_USER_ID
                    }
                }
            }
        }
        stage('Check string') {
            steps {
                script {
                    try {
                        if (params.DEPLOY_OWNER.substring(0,12) == 'staging-auto') {
                            println params.DEPLOY_OWNER.substring(0,12)
                            println params.DEPLOY_OWNER.replaceAll('staging-auto-', '')
                            stage_deploy_branch_name = params.DEPLOY_OWNER.replaceAll('staging-auto-', '')
                            stage_auto_proceed = true
                            platform_process = true
                            this_environment = 'STAGING'
                            if (params.DEPLOY_OWNER.replaceAll('staging-auto-', '') == 'master') {
                                this_platform_branch = 'master'
                                theme_process = true
                            } else {
                                this_platform_branch = params.DEPLOY_OWNER.replaceAll('staging-auto-', '')
                                theme_process = false
                            }
                            send_slack_message(stage_deploy_branch_name, 'start')
                        }
                    } catch (err) {
                        println err
                    }
                }
            }
        }
        stage('Choose environment') {
            when {
                expression { return stage_auto_proceed == false }
            }
            steps {
                script {
                    try {
                        timeout(time: 2) {
                            this_environment = input message: "which environment to run", parameters: [choice(name: 'environment', choices: ['PROD', 'STAGING', 'PREPROD'], description: 'which environment to run')]
                        }
                    } catch (err) {
                        println err
                        proceed = false
                        manual = false
                    }
                }
            }
        }
        stage('Choose Process') {
            when {
                expression { return proceed == true && stage_auto_proceed == false }
            }
            steps {
                script {
                    try {
                        timeout(time: 2) {
                            this_process = choose_environment(this_environment)
                            println this_process
                            if (this_process == 'platform') {
                                platform_process = true
                            } else if (this_process == 'theme') {
                                theme_process = true
                                if (this_environment == 'PROD') {
                                    sub_theme_process = input message: "which sub-process to run", parameters: [choice(name: 'process', choices: ['compile', 'deploy'], description: 'which sub-process to run')]
                                    if (sub_theme_process == 'compile') {
                                        theme_compile_process = true
                                    } else if (sub_theme_process == 'deploy') {
                                        theme_deploy_process = true
                                    }
                                } else if (this_environment in ['STAGING', 'PREPROD']) {
                                    theme_compile_process = false
                                    theme_deploy_process = true
                                    sub_theme_process = input message: "which part to compile", parameters: [choice(name: 'process', choices: ['lms', 'cms'], description: 'which part to compile')]
                                }
                            } else if (this_process == 'platform&theme') {
                                platform_process = true
                                theme_process = true
                                theme_compile_process = false
                                theme_deploy_process = true
                                platform_with_theme_process = true
                                sub_theme_process = input message: "which app theme to compile", parameters: [choice(name: 'process', choices: ['lms', 'cms'], description: 'which app theme to compile')]
                            } else if (this_process == 'restart service') {
                                restart_service_process = true
                                sub_restart_service_process = input message: "which service to restart", parameters: [choice(name: 'service', choices: ['all', 'edxapp', 'lms'], description: 'which service to restart')]
                                if (sub_restart_service_process == 'all') {
                                    tag_restart_service = 'restart-all'
                                } else if (sub_restart_service_process == 'edxapp') {
                                    tag_restart_service = 'restart-edxapp'
                                } else if (sub_restart_service_process == 'lms') {
                                    tag_restart_service = 'restart-lms'
                                }
                            } else if (this_process == 'certs') {
                                certs_process = true
                                if (this_environment in ['STAGING', 'PREPROD']) {
                                    stage_certs_process = true
                                }
                            } else if (this_process == 'xblock') {
                                xblock_process = true
                                if (this_environment in ['STAGING', 'PREPROD']) {
                                    stage_xblock_process = true
                                }
                            } else if (this_process == 'config file') {
                                config_file_process = true
                                sub_config_file_process = input message: "which service to update configuration file", parameters: [choice(name: 'service', choices: ['nginx', 'platform'], description: 'which service to update configuration file')]
                                if (sub_config_file_process == 'nginx') {
                                    tag_config_file = 'update_nginx'
                                } else if (sub_config_file_process == 'platform') {
                                    tag_config_file = 'update_platform'
                                }
                            } else if (this_process == 'revert platform code') {
                                revert_process = true
                            }
                        }   
                    } catch (err) {
                        proceed = false
                    }
                } 
            }
        }
        stage('Set stage tenant host') {
            when {
                expression { return proceed == true && this_environment == 'STAGING'}
            }
            steps {
                script {
                    instance_ip = '13.250.89.243,'
                    ec2_location = 'ap-southeast-1'
                }
            }
        }
        stage('Set preprod tenant host') {
            when {
                expression { return proceed == true && this_environment == 'PREPROD' }
            }
            steps {
                script {
                    instance_ip = '52.212.106.25,'
                    ec2_location = 'eu-west-1'
                }
            }
        }
        stage('Get tenant host') {
            when {
                expression { return proceed == true && this_environment == 'PROD' && stage_auto_proceed == false }
            }
            steps {
                script {
                    try {
                        timeout(time: 2) {
                            if (true) {
                                ec2_location = choose_region()
                                println ec2_location
                                (tenant_list_parameters, tenant_list) = choose_tenant()
                                println tenant_list_parameters
                                println tenant_list
                                chooseOptions = input(id: 'chooseOptions', message: 'Select tenant options', parameters: tenant_list_parameters)
                                for (item in chooseOptions) {
                                    if (item.key == 'ALL' && item.value == true) {
                                        instance_ip = ''
                                        for (i in tenant_list) {
                                            for (int j = 1; j < i.size(); j++) {
                                                instance_ip += i[j]
                                                instance_ip += ','
                                            }
                                        }
                                        break
                                    }
                                    if (item.value == true) {
                                        for (i in tenant_list) {
                                            if (i[0] == item.key) {
                                                for (int j = 1; j < i.size(); j++) {
                                                instance_ip += i[j]
                                                instance_ip += ','
                                                }
                                            }
                                        }
                                    }
                                }
                                println instance_ip
                                if (instance_ip == '') {
                                    proceed = false
                                }
                                this_platform_branch = 'master-master'
                            } else {
                                proceed = false
                            }
                        } 
                    } catch (err) {
                        proceed = false
                    }
                }
            }
        }
        stage('Process platform') {
            stages {
                stage('Set platform branch name') {
                    when {
                        expression { return proceed == true && this_environment in ['STAGING', 'PREPROD'] && platform_process == true && stage_auto_proceed == false }
                    }
                    steps {
                        script {
                            try {
                                timeout(time: 2) {
                                    def list_platform_branches = []
                                    platform_branchout = sh script: "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_edxapp/files/get_platform_branch_list.py", returnStdout: true
                                    for (i in platform_branchout.split('\n')) {
                                        list_platform_branches.add(i)
                                    }
                                    print list_platform_branches
                                    this_platform_branch = input message: "which branch to deploy", parameters: [choice(name: 'branch', choices: list_platform_branches, description: 'which branch to deploy')]
                                    println this_platform_branch
                                }
                            } catch (err) {
                                println err
                                proceed = false
                            }
                        }
                    }
                }
                stage("Get migrate DB or not") {
                    when {
                        expression { return proceed == true && platform_process == true && stage_auto_proceed == false }
                    }
                    steps {
                        script {
                            try {
                                timeout(time:2) {
                                    dbMigrate = input message: "Run Migrate DB", parameters: [choice(name: 'migrate_db', choices: ['no', 'yes'], description: 'Run Migrate DB')]
                                    println dbMigrate
                                }
                            } catch (err) {
                                proceed = false
                            }
                        }
                    }
                }
                stage("Get run npm install or not") {
                    when {
                        expression { return proceed == true && platform_process == true && stage_auto_proceed == false}
                    }
                    steps {
                        script {
                            try {
                                timeout(time:2) {
                                    nodeInstall = input message: "Run 'npm install' command", parameters: [choice(name: 'installl_node', choices: ['no', 'yes'], description: 'Run Install Node')]
                                    println nodeInstall
                                }
                            } catch (err) {
                                println err
                                proceed = false
                                throw err
                            }
                        }
                    }
                }
                stage("Get run translation script or not") {
                    when {
                        expression { return proceed == true && platform_process == true && stage_auto_proceed == false}
                    }
                    steps {
                        script {
                            try {
                                timeout(time:2) {
                                    runTranslation = input message: "Run translation script", parameters: [choice(name: 'run_translation', choices: ['no', 'yes'], description: 'Run Translation Script')]
                                    println runTranslation
                                }
                                if (runTranslation == 'yes') {
                                    theme_process = true
                                    translation_theme_process = true
                                }
                            } catch (err) {
                                println err
                                proceed = false
                                throw err
                            }
                       }
                    }
                }
                stage("Deploy") {
                    when {
                        expression { return proceed == true && platform_process == true && platform_with_theme_process == false }
                    }
                    steps {
                        dir('configuration/playbooks') {
                            script {
                                if (stage_auto_proceed == false) {
                                    restart_service_process = true
                                    tag_restart_service = 'restart-all'
                                    if (this_platform_branch == 'master-master') {
                                        if ( lt_user_id == 'yves' ) {
                                            commit_id = input message: "Input Commit ID", parameters: [string(name:'id:', defaultValue: 'NONE', description: 'Which commit ID to deploy')]
                                            if (commit_id != 'NONE') {
                                                println commit_id
                                                sh """
                                                . /tmp/.venvec2/bin/activate
                                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy-production-commitid"  -e "edx_platform_commitid=${commit_id}" -e "migrate_lt_db=${dbMigrate}" -e "run_npm_install=${nodeInstall}" -e "run_trans_script=${runTranslation}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                                """
                                            } else {
                                                if ( ec2_location == 'azure' ) {
                                                    sh """
                                                    . /tmp/.venvec2/bin/activate
                                                    ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "azure-deploy-production" -e "migrate_lt_db=${dbMigrate}" -e "run_npm_install=${nodeInstall}" -e "run_trans_script=${runTranslation}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                                    """
                                                } else {
                                                    sh """
                                                    . /tmp/.venvec2/bin/activate
                                                    ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy-production" -e "migrate_lt_db=${dbMigrate}" -e "run_npm_install=${nodeInstall}" -e "run_trans_script=${runTranslation}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                                    """   
                                                }
                                                
                                            }
                                        } else {
                                            if ( ec2_location == 'azure' ) {
                                                sh """
                                                . /tmp/.venvec2/bin/activate
                                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "azure-deploy-production" -e "migrate_lt_db=${dbMigrate}" -e "run_npm_install=${nodeInstall}" -e "run_trans_script=${runTranslation}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                                """
                                            } else {
                                                sh """
                                                . /tmp/.venvec2/bin/activate
                                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy-production" -e "migrate_lt_db=${dbMigrate}" -e "run_npm_install=${nodeInstall}" -e "run_trans_script=${runTranslation}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                                """
                                            }
                                        }
                                    } else {
                                        sh """
                                        . /tmp/.venvec2/bin/activate
                                        ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy" -e "edx_platform_version=${this_platform_branch}" -e "migrate_lt_db=${dbMigrate}" -e "run_npm_install=${nodeInstall}"  -e "run_trans_script=${runTranslation}" lt_pipeline_jobs.yml
                                        """
                                    }
                                } else if (stage_auto_proceed == true) {
                                    restart_service_process = true
                                    tag_restart_service = 'restart-all'
                                    sh """
                                    . /tmp/.venvec2/bin/activate
                                    ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy" -e "edx_platform_version=${this_platform_branch}" -e "migrate_lt_db=no" -e "run_npm_install=no" -e "run_trans_script=no" lt_pipeline_jobs.yml
                                    """
                                }
                            }
                        }
                    }
                }
                stage("Revert code") {
                    when {
                        expression { return proceed == true && revert_process == true }
                    }
                    steps {
                        dir('configuration/playbooks') {
                            script {
                                restart_service_process = true
                                tag_restart_service = 'restart-all'
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "revert-production" -e "migrate_lt_db=no" -e "run_npm_install=no" -e "run_trans_script=no" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                """
                            }
                        }
                    }
                }
            }
        }
        stage('Process theme') {
            stages {
                stage("Get theme folder") {
                    when {
                        expression { return proceed == true && theme_process == true && theme_compile_process == true && theme_deploy_process == false && stage_auto_proceed == false }
                    }
                    steps {
                        script {
                            try {
                                timeout(time:2) {
                                    get_app = input message: "Which APP to Compile", parameters: [choice(name: 'compile_app', choices: ['lms', 'cms', 'lms+cms'], description: 'Which APP to Compile')]
                                    if (get_app == 'lms') {
                                        tag_theme = 'lms-theme'
                                    } else if (get_app == 'cms') {
                                        tag_theme = 'cms-theme'
                                    } else if (get_app == 'lms+cms') {
                                        tag_theme = 'all-theme'
                                    } else {
                                        proceed = false
                                    }
                                }
                            } catch (err) {
                                proceed = false
                            }
                        }
                    }
                }
                stage("Set theme folder") {
                    when {
                        expression { return proceed == true && theme_process == true && theme_compile_process == false && theme_deploy_process == true && stage_auto_proceed == false }
                    }
                    steps {
                        script {
                            try {
                                timeout(time: 2) {
                                    def list_branches = []
                                    branchout = sh script: "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_theme/files/get_theme_branch_list.py", returnStdout: true
                                    for (i in branchout.split('\n')) {
                                        def parameter_boolean3 = [$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: i]
                                        list_branches.add(parameter_boolean3)
                                    }
                                    chooseOptions3 = input(id: 'chooseOptions3', message: 'Select theme branch options', parameters: list_branches)
                                    for (item in chooseOptions3) {
                                        if (item.value == true) {
                                            compile_theme.add(item.key)
                                            tag_theme = 'deploy-theme'
                                        }
                                    }
                                    println compile_theme
                                    if (this_environment in ['STAGING', 'PREPROD']) {
                                        if (sub_theme_process == 'lms') {
                                            tag_theme = 'stage-theme-lms'
                                        } else if (sub_theme_process == 'cms') {
                                            tag_theme = 'stage-theme-cms'
                                        }
                                    }
                                    if (compile_theme == []) {
                                        proceed = false
                                    }
                                }
                            } catch (err) {
                                println err
                                proceed = false
                            }
                        }
                    }
                }
                stage("Deploy platform with theme") {
                    when {
                        expression { return proceed == true && platform_process == true && platform_with_theme_process == true }
                    }
                    steps {
                        script {
                            restart_service_process = true
                            tag_restart_service = 'restart-all'
                        }
                        dir('configuration/playbooks') {
                            sh """
                            . /tmp/.venvec2/bin/activate
                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy" -e "edx_platform_version=${this_platform_branch}" -e "migrate_lt_db=${dbMigrate}" -e "run_npm_install=${nodeInstall}" -e "run_trans_script=${runTranslation}" lt_pipeline_jobs.yml
                            """                    
                        }
                    }
                }
                stage("Compile theme") {
                    when {
                        expression { return proceed == true && theme_process == true }
                    }
                    steps {
                        dir('configuration/playbooks') {
                            script {
                                restart_service_process = true
                                tag_restart_service = 'restart-all'
                                if (stage_auto_proceed == false && translation_theme_process == false) {
                                    if ( lt_user_id == 'yves') {
                                        commit_id = input message: "Input Commit ID", parameters: [string(name:'id:', defaultValue: 'NONE', description: 'Which commit ID to deploy')]
                                        if ( commit_id != 'NONE') {
                                            println commit_id
                                            if ( ec2_location == 'azure' ) {
                                                sh """
                                                . /tmp/.venvec2/bin/activate
                                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_theme}-azure-commitid" -e "{'LT_THEME': ${compile_theme}}" -e "lt_ec2_region=${ec2_location}" -e "theme_commitid=${commit_id}" lt_pipeline_jobs.yml
                                                """
                                            } else {
                                                sh """
                                                . /tmp/.venvec2/bin/activate
                                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_theme}-commitid" -e "{'LT_THEME': ${compile_theme}}" -e "lt_ec2_region=${ec2_location}" -e "theme_commitid=${commit_id}" lt_pipeline_jobs.yml
                                                """
                                            }
                                        } else {
                                            if ( ec2_location == 'azure' ) {
                                                sh """
                                                . /tmp/.venvec2/bin/activate
                                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_theme}-azure" -e "{'LT_THEME': ${compile_theme}}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                                """
                                            } else {
                                                sh """
                                                . /tmp/.venvec2/bin/activate
                                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_theme}" -e "{'LT_THEME': ${compile_theme}}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                                """
                                            }
                                        }
                                    } else {
                                        if ( ec2_location == 'azure' ) {
                                            sh """
                                            . /tmp/.venvec2/bin/activate
                                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_theme}-azure" -e "{'LT_THEME': ${compile_theme}}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                            """
                                        } else {
                                            sh """
                                            . /tmp/.venvec2/bin/activate
                                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_theme}" -e "{'LT_THEME': ${compile_theme}}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                            """
                                        }                                       
                                    } 
                                } else if (stage_auto_proceed == false && translation_theme_process == true) {
                                    if (this_environment == 'PROD') {
                                        if ( ec2_location == 'azure' ) {
                                            sh """
                                            . /tmp/.venvec2/bin/activate
                                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "all-theme-azure" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                            """
                                        } else {
                                            sh """
                                            . /tmp/.venvec2/bin/activate
                                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "all-theme" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                            """   
                                        }
                                        
                                    } else if (this_environment in ['STAGING', 'PREPROD']) {
                                        if (platform_with_theme_process == false) {
                                            sh """
                                            . /tmp/.venvec2/bin/activate
                                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "all-theme" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                            """
                                        } else if (platform_with_theme_process == true) {
                                            sh """
                                            . /tmp/.venvec2/bin/activate
                                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_theme}" -e "{'LT_THEME': ${compile_theme}}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                            """
                                        }
                                    }
                                } else if (stage_auto_proceed == true) {
                                    sh """
                                    . /tmp/.venvec2/bin/activate
                                    ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "stage-auto-theme" -e "{'LT_THEME': ['hawthorn']}" lt_pipeline_jobs.yml
                                    """
                                }
                            }
                        }
                    }
                }
            }
        }
        stage("Set certificates branch name") {
            when {
                expression { return proceed == true && certs_process == true && stage_certs_process == true }
            }
            steps {
                script {
                    try {
                        timeout(time: 2) {
                            def list_certs_branchs = []
                            branchout3 = sh script: "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_certs/files/get_certs_branch_list.py", returnStdout: true
                            for (i in branchout3.split('\n')) {
                                list_certs_branchs.add(i)
                            }
                            certs_branch_name = input message: 'Select certificates branch options', parameters: [choice(name: 'branch', choices: list_certs_branchs, description: 'which branch to deply')]
                            println certs_branch_name
                        }                       
                    } catch (err) {
                        println err
                        proceed = false
                        throw err
                    }
                }
            }
        }
        stage("Deploy certificates") {
            when {
                expression { return proceed == true && certs_process == true }
            }
            steps {
                script {
                    restart_service_process = true
                    tag_restart_service = 'restart-all'
                }
                dir('configuration/playbooks') {
                    script {
                        if (lt_user_id == 'yves') {
                            commit_id = input message: "Input Commit ID", parameters: [string(name:'id:', defaultValue: 'NONE', description: 'Which commit ID to deploy')]
                            if (commit_id != 'NONE') {
                                println commit_id
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy-certs-commitid" -e "certs_commitid=${commit_id}" lt_pipeline_jobs.yml
                                """
                            } else {
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy-certs" -e '@${env.WORKSPACE}/inventory/group_vars/tenants/certs-vars.yml' lt_pipeline_jobs.yml
                                """
                            }
                        } else {
                            if (this_environment == 'PROD') {
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy-certs" -e '@${env.WORKSPACE}/inventory/group_vars/tenants/certs-vars.yml' lt_pipeline_jobs.yml
                                """   
                            } else if (this_environment in ['STAGING', 'PREPROD']) {
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "stage-deploy-certs" -e '@${env.WORKSPACE}/inventory/group_vars/tenants/certs-vars.yml' -e "{'branch_name':${certs_branch_name}}" lt_pipeline_jobs.yml
                                """
                            }
                        }
                    }
                }
            }
        }
        stage("Set xblock name") {
            when {
                expression { return proceed == true && xblock_process == true }
            }
            steps {
                script {
                    try {
                        timeout(time: 2) {
                            def list_repoes = []
                            repoout = sh script: "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_xblock/files/get_xblock_repo_list.py", returnStdout: true
                            for (i in repoout.split('\n')) {
                                list_repoes.add(i)
                            }
                            xblock_name = input message: 'Select xblock repo options', parameters: [choice(name: 'repo', choices: list_repoes, description: 'which repository xblock to depoly')]
                            println xblock_name
                        }
                    } catch (err) {
                        println err
                        proceed = false
                        throw err
                    }
                }
            }
        }
        stage("Set xblock branch name") {
            when {
                expression { return proceed == true && xblock_process == true && stage_xblock_process == true }
            }
            steps {
                script {
                    try {
                        timeout(time: 2) {
                            def list_xblock_branchs = []
                            branchout2 = sh script: "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_xblock/files/get_xblock_branch_list.py ${xblock_name}", returnStdout: true
                            for (i in branchout2.split('\n')) {
                                list_xblock_branchs.add(i)
                            }
                            xblock_branch_name = input message: 'Select xblock branch options', parameters: [choice(name: 'branch', choices: list_xblock_branchs, description: 'which branch to deply this xblock')]
                            println xblock_branch_name
                        }                       
                    } catch (err) {
                        println err
                        proceed = false
                        throw err
                    }
                }
            }
        }
        stage("Deploy xblock") {
            when {
                expression { return proceed == true && xblock_process == true }
            }
            steps {
                script {
                    restart_service_process = true
                    tag_restart_service = 'restart-all'
                }
                dir('configuration/playbooks') {
                    script {
                    if (lt_user_id == 'yves') {
                        commit_id = input message: "Input Commit ID", parameters: [string(name:'id:', defaultValue: 'NONE', description: 'Which commit ID to deploy')]
                        if (commit_id != 'NONE') {
                            println commit_id
                            sh """
                            . /tmp/.venvec2/bin/activate
                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" -e "xblock_commitid=${commit_id}" -e "{'xblock_name':${xblock_name}}" --tags "deploy-xblock-commitid" lt_pipeline_jobs.yml
                            """
                        } else {
                            sh """
                            . /tmp/.venvec2/bin/activate
                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" -e "{'xblock_name':${xblock_name}}" --tags "deploy-xblock" lt_pipeline_jobs.yml
                            """
                        }
                    } else {
                        if ( this_environment == 'PROD') {
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" -e "{'xblock_name':${xblock_name}}" --tags "deploy-xblock" lt_pipeline_jobs.yml
                                """
                            }
                            else if ( this_environment in ['STAGING', 'PREPROD'] ) {
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" -e "{'xblock_name':${xblock_name}}" -e "{'branch_name': ${xblock_branch_name}}" --tags "stage-deploy-xblock" lt_pipeline_jobs.yml
                                """
                            }
                    }
                    }
                    
                }
            }
        }
        stage("Update configuration file") {
            when {
                expression { return proceed == true && config_file_process == true }
            }
            steps {
                dir('configuration/playbooks') {
                    script {
                        if (sub_config_file_process == 'nginx') {
                            sh """
                            . /tmp/.venvec2/bin/activate
                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}"  --tags "${tag_config_file}" lt_pipeline_jobs.yml
                            """
                        } else if (sub_config_file_process == 'platform') {
                            restart_service_process = true
                            tag_restart_service = 'restart-all'
                            sh """
                            . /tmp/.venvec2/bin/activate
                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}"  --tags "${tag_config_file}" lt_pipeline_jobs.yml
                            """
                        }
                    }
                }
            }
        }
        stage("Restart service") {
            when {
                expression { return proceed == true && restart_service_process == true }
            }
            steps {
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venvec2/bin/activate
                    ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_restart_service}" lt_pipeline_jobs.yml
                    """ 
                }
            }
        }
    }
    post {
        aborted {
            script {
                if (manual == false && stage_auto_proceed == false) {
                    githubNotify status: 'PENDING', description: 'waiting for deploy at stage server'
                    println 'aborted'
                }
            }
        }
        failure {
            script {
                if (stage_auto_proceed == true) {
                    githubNotify status: 'FAILURE', description: ' failed deploy at stage server'
                    println 'failure'
                    send_slack_message(stage_deploy_branch_name, 'failure_end')
                }
            }
        }
        success {
            script {
                if (stage_auto_proceed == true) {
                    githubNotify status: 'SUCCESS', description: ' done deploy at stage server'
                    println 'success'
                    send_slack_message(stage_deploy_branch_name, 'success_end')
                }
            }
        }
        always {
            script {
                if (proceed == true && manual == true) {
                    currentBuild.result = "SUCCESS"
                    echo "RESULT: ${currentBuild.result}"
                } else if (proceed == false && manual == false) {
                    currentBuild.result = 'ABORTED'
                    echo "RESULT: ${currentBuild.result}"
                } else if (proceed == false) {
                    currentBuild.result = "FAILURE"
                    echo "RESULT: ${currentBuild.result}"
                }
            }
        }
    }
}
