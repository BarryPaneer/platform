pipeline {
    agent any
    options {
        timestamps()
    }
    environment {
        BUILD_TAG = "${env.BUILD_TAG.toLowerCase()}"
    }
    stages {
        stage("Stop Old Build") {
            steps {
                milestone label: "", ordinal:  Integer.parseInt(env.BUILD_ID) - 1
                milestone label: "", ordinal:  Integer.parseInt(env.BUILD_ID)
            }
        }
        stage("Test") {
            steps {
                sh "BUILD_TAG=${BUILD_TAG} make ci_up"
                sh "BUILD_TAG=${BUILD_TAG} make ci_test"
                junit "reports/**/nosetests.xml"
                cobertura coberturaReportFile: "reports/coverage.xml", failUnstable: false, maxNumberOfBuilds: 20, onlyStable: false, zoomCoverageChart: false
            }
            post {
                always {
                    sh "BUILD_TAG=${BUILD_TAG} make ci_clean || true"
                    sh "BUILD_TAG=${BUILD_TAG} make ci_down || true"
                    sh "sudo chown -R jenkins:jenkins ${env.WORKSPACE} || true"
                }
            }
        }
    }
    post {
        success {
            script {
                if (env.BRANCH_NAME == "master") {
                    build job: "/ci-pipeline-deploy/master", parameters: [[$class: "StringParameterValue", name: "DEPLOY_OWNER", value: "staging-auto-master"]], wait: false
                } else {
                    build job: "/ci-pipeline-deploy/${env.CHANGE_BRANCH}", parameters: [[$class: "StringParameterValue", name: "DEPLOY_OWNER", value: "staging-auto-${env.CHANGE_BRANCH}"]], wait: false
                }
            }
        }
    }
}
