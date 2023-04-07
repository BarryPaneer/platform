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
def platform_with_theme_process = false
def restart_service_process = false
def certs_process = false
def xblock_process = false
def config_file_process = false
def proceed = true
def manual = true
def stage_auto_proceed = false
def this_environment = ''
def sub_theme_process = ''
def sub_restart_service_process = ''
def this_platform_branch = ''
def key_file = '/opt/password.txt'
def ec2_location = null
def instance_ip = ""
def compile_theme = []
def xblock_name = []
def tag_theme = ''
def tag_restart_service = ''
def tag_config_file = ''


pipeline {
    agent { node { label 'master' } }
    options {
        timestamps()
    }
    environment {
        AWS_ACCESS_KEY_ID     = credentials('jenkins-aws-cn-secret-key-id')
        AWS_SECRET_ACCESS_KEY = credentials('jenkins-aws-cn-secret-access-key')
        GITHUB_USERNAME       = credentials('jenkins-github-username')
        GITHUB_PASSWORD       = credentials('jenkins-github-password')  
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
        stage('Choose environment') {
            when {
                expression { return stage_auto_proceed == false }
            }
            steps {
                script {
                    try {
                        timeout(time: 2) {
                            this_environment = input message: "which environment to run", parameters: [choice(name: 'environment', choices: ['PROD'], description: 'which environment to run')]
                        }
                    } catch (err) {
                        println err
                        proceed = false
                        manual = false
                        throw err
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
                            if (this_environment == 'PROD') {
                                this_process = input message: "which process to run", parameters: [choice(name: 'process', choices: ['platform', 'theme', 'restart serivce', 'xblock', 'certs', 'config file'], description: 'which process to run')]
                            } else if (this_environment == 'STAGING') {
                                this_process = input message: "which process to run", parameters: [choice(name: 'process', choices: ['platform', 'theme', 'platform&theme', 'restart serivce', 'xblock', 'certs', 'config file'], description: 'which process to run')]
                            }
                            if (this_process == 'platform') {
                                platform_process = true
                            } else if (this_process == 'theme') {
                                theme_process = true
                                if (this_environment == 'PROD') {
                                    sub_theme_process = input message: "which sub-process to run", parameters: [choice(name: 'process', choices: ['compile', 'deploy'], description: 'which sub-process to run')]
                                    if (sub_theme_process == 'compile') {
                                        theme_compile_process = true
                                    } else if (sub_theme_process == 'deploy') {
                                        theme_compile_process = false
                                    }
                                } else if (this_environment == 'STAGING') {
                                    theme_compile_process = false
                                    sub_theme_process = input message: "which part to compile", parameters: [choice(name: 'process', choices: ['lms', 'cms'], description: 'which part to compile')]
                                }
                            } else if (this_process == 'platform&theme') {
                                platform_process = true
                                theme_process = true
                                theme_compile_process = false
                                platform_with_theme_process = true
                                sub_theme_process = input message: "which app theme to compile", parameters: [choice(name: 'process', choices: ['lms', 'cms'], description: 'which app theme to compile')]
                            } else if (this_process == 'restart serivce') {
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
                            } else if (this_process == 'xblock') {
                                xblock_process = true
                            } else if (this_process == 'config file') {
                                config_file_process = true
                                sub_config_file_process = input message: "which service to update configuration file", parameters: [choice(name: 'service', choices: ['nginx', 'platform'], description: 'which service to update configuration file')]
                                if (sub_config_file_process == 'nginx') {
                                    tag_config_file = 'update_nginx'
                                } else if (sub_config_file_process == 'platform') {
                                    tag_config_file = 'update_platform'
                                }
                            }
                        }
                    } catch (err) {
                        println err
                        proceed = false
                        throw err
                    }
                } 
            }
        }
        stage('Set tenant host') {
            when {
                expression { return proceed == true && this_environment == 'STAGING' }
            }
            steps {
                script {
                    instance_ip = '13.250.89.243,'
                    ec2_location = 'ap-southeast-1'
                }
            }
        }
        stage('Set platform branch name') {
            when {
                expression { return proceed == true && this_environment == 'STAGING' && platform_process == true && stage_auto_proceed == false}
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
                            this_platform_branch = input message: "which platform branch to deploy", parameters: [choice(name: 'branch', choices: list_platform_branches, description: 'which platform branch to deploy')]
                        }
                    } catch (err) {
                        println err
                        proceed = false
                        throw err
                    }
                }
            }
        }
        stage('Get tenant host') {
            when {
                expression { return proceed == true && this_environment == 'PROD' && stage_auto_proceed == false}
            }
            steps {
                script {
                    try {
                        timeout(time: 2) {
                            if (env.BRANCH_NAME == "master") {
                                ec2_region = input message: "which region to deploy", parameters: [choice(name: 'region', choices: ['CN'],description: 'which region to deploy')]
                                if (ec2_region == 'CN') {
                                    ec2_location = 'cn-northwest-1'
                                    this_platform_branch = 'master-master'
                                } 
                                println ec2_location
                                sh "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_edxapp/files/check_tenant_file.py ${env.WORKSPACE}/inventory ${ec2_location} ${env.WORKSPACE}/configuration/playbooks/roles/lt_edxapp/files/credential-helper.sh"
                                def list_parameters = []
                                def list_tenant = []
                                tenantout = sh script: "python ${env.WORKSPACE}/configuration/playbooks/roles/lt_edxapp/files/get_tenant_list.py ${env.WORKSPACE}/inventory/hosts.ini ${ec2_location}", returnStdout: true
                                for (item in tenantout.split('\n')) {
                                    def sub_item_list = []
                                    for (i in item.split(',')) {
                                        sub_item_list.add(i)
                                    }
                                    list_tenant.add(sub_item_list)
                                }
                                println list_tenant
                                for (item in list_tenant) {
                                    def parameter_boolean = [$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: item[0]]
                                    list_parameters.add(parameter_boolean)
                                }
                                list_parameters.add([$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: 'ALL'])
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
                                print instance_ip
                                if (instance_ip == '') {
                                    proceed = false
                                }
                            } else {
                                proceed = false
                            }
                        } 
                    } catch (err) {
                        println err
                        proceed = false
                        throw err
                    }
                }
            }
        }
        stage("Get migrate DB or not") {
            when {
                expression { return proceed == true && platform_process == true && stage_auto_proceed == false}
            }
            steps {
                script {
                    try {
                        timeout(time:2) {
                            dbMigrate = input message: "Run Migrate DB", parameters: [choice(name: 'migrate_db', choices: ['no', 'yes'], description: 'Run Migrate DB')]
                            println dbMigrate
                        }
                    } catch (err) {
                        println err
                        proceed = false
                        throw err
                    }
                }
            }
        }
        stage("Deploy platform") {
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
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy-production" -e "migrate_lt_db=${dbMigrate}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                                """
                            } else {
                                sh """
                                . /tmp/.venvec2/bin/activate
                                ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy" -e "edx_platform_version=${this_platform_branch}" -e "migrate_lt_db=${dbMigrate}" lt_pipeline_jobs.yml
                                """
                            }                            
                        } else if (stage_auto_proceed == true) {
                            restart_service_process = true
                            tag_restart_service = 'restart-all'
                            sh """
                            . /tmp/.venvec2/bin/activate
                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy" -e "edx_platform_version=${this_platform_branch}" -e "migrate_lt_db=yes" lt_pipeline_jobs.yml
                            """
                        }
                    }
                    
                }
            }
        }
        stage("Get theme folder") {
            when {
                expression { return proceed == true && theme_process == true && theme_compile_process == true && stage_auto_proceed == false }
            }
            steps {
                script {
                    try {
                        timeout(time:2) {
                            def folder_stdout = ''
                            for (ip in instance_ip.split(',')) {
                                folderout = sh script: "ssh -i /opt/instanceskey/${ec2_location}_platform_key.pem ubuntu@${ip} 'ls /edx/app/edxapp/themes/'", returnStdout: true
                                folder_stdout += folderout
                            }
                            def list_theme = [] 
                            def list_themes = []
                            for (i in folder_stdout.split('\n')) {
                                list_theme.add(i)
                            }
                            list_theme = list_theme.unique()
                            for (theme_folder in list_theme) {
                                def parameter_boolean2 = [$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: theme_folder]
                                list_themes.add(parameter_boolean2)
                            }
                            list_themes.add([$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: 'CMS'])
                            list_themes.add([$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: 'ALL'])
                            chooseOptions2 = input(id: 'chooseOptions2', message: 'Select theme options', parameters: list_themes)
                            for (item in chooseOptions2) {
                                if (item.key == 'ALL' && item.value == true) {
                                    compile_theme = list_theme
                                    tag_theme = 'all-theme'
                                    break
                                }
                                if (item.key == 'CMS' && item.value == true) {
                                    def cms_folder_name = ''
                                    compile_theme = []
                                    cms_folder_name = 'hawthorn-' + ec2_region.toLowerCase()
                                    compile_theme.add(cms_folder_name)
                                    tag_theme = 'cms-theme'
                                    break
                                }
                                if (item.value == true) {
                                    compile_theme.add(item.key)
                                    tag_theme = 'lms-theme'
                                }
                            }
                            print compile_theme
                            if (compile_theme == []) {
                                proceed = false
                            }
                        }
                    } catch (err) {
                        println err
                        proceed = false
                        throw err
                    }
                }
            }
        }
        stage("Set theme folder") {
            when {
                expression { return proceed == true && theme_process == true && theme_compile_process == false && stage_auto_proceed == false}
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
                            if (this_environment == 'STAGING') {
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
                        throw err
                    }
                }
            }
        }
        stage("Deploy platform with theme") {
            when {
                expression { return proceed == true && platform_process == true && platform_with_theme_process == true && stage_auto_proceed == false }
            }
            steps {
                script {
                    restart_service_process = true
                    tag_restart_service = 'restart-all'
                }
                dir('configuration/playbooks') {
                    sh """
                    . /tmp/.venvec2/bin/activate
                    ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy" -e "edx_platform_version=${this_platform_branch}" -e "migrate_lt_db=${dbMigrate}" lt_pipeline_jobs.yml
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
                        tag_restart_service = 'restart-edxapp'
                        if (stage_auto_proceed == false) {
                            sh """
                            . /tmp/.venvec2/bin/activate
                            ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "${tag_theme}" -e "{'LT_THEME': ${compile_theme}}" -e "lt_ec2_region=${ec2_location}" lt_pipeline_jobs.yml
                            """
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
                    sh """
                    . /tmp/.venvec2/bin/activate
                    ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" --tags "deploy-certs" lt_pipeline_jobs.yml
                    """
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
                                def parameter_boolean4 = [$class: 'BooleanParameterDefinition', defaultValue: false, description: '', name: i]
                                list_repoes.add(parameter_boolean4)
                            }
                            chooseOptions4 = input(id: 'chooseOptions4', message: 'Select xblock repo options', parameters: list_repoes)
                            for (item in chooseOptions4) {
                                if (item.value == true) {
                                    xblock_name.add(item.key)
                                }
                            }
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
                    sh """
                    . /tmp/.venvec2/bin/activate
                    ansible-playbook -i "${instance_ip}" -u ubuntu --private-key /opt/instanceskey/"${ec2_location}"_platform_key.pem --vault-password-file "${key_file}" -e "{'xblock_name':${xblock_name}}" --tags "deploy-xblock" lt_pipeline_jobs.yml
                    """
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
                            tag_restart_service = 'restart-edxapp'
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
                }
            }
        }
        success {
            script {
                if (stage_auto_proceed == true) {
                    githubNotify status: 'SUCCESS', description: ' done deploy at stage server'
                    println 'success'
                }
            }
        }
    }
}
