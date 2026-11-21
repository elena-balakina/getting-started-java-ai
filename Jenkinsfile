pipeline {
    agent {
        label 'js-node24-jenkins-warm-agent-1'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
    }

    environment {
        SELENOID_URL = 'https://selenoid.qa.guru/wd/hub'
        BROWSER_VERSION = '157.0'
        ALLURE_VERSION = '2.46.1'
        ALLURE_SHA256 = '37428164f310c8d137cfdd2c3a25d049b233261ddab13e1bd4dfd7627b5cbf8d'
        TOOLS_DIR = "${WORKSPACE}/.ci-tools"
        ALLURE_BIN = "${WORKSPACE}/.ci-tools/allure-2.46.1/bin/allure"
        COMPILE_OUTCOME = 'not_run'
        TEST_OUTCOME = 'not_run'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare tools') {
            steps {
                sh '''
                    set -eu
                    mkdir -p "$TOOLS_DIR"

                    allure_archive="$TOOLS_DIR/allure-commandline-$ALLURE_VERSION.tgz"

                    curl -fsSL -o "$allure_archive" \\
                      "https://repo.maven.apache.org/maven2/io/qameta/allure/allure-commandline/$ALLURE_VERSION/allure-commandline-$ALLURE_VERSION.tgz"
                    echo "$ALLURE_SHA256  $allure_archive" | sha256sum --check --strict

                    rm -rf "$TOOLS_DIR/allure-$ALLURE_VERSION"
                    tar -xzf "$allure_archive" -C "$TOOLS_DIR"
                    chmod +x "$ALLURE_BIN"

                    allure_version=$("$ALLURE_BIN" --version)
                    test "$allure_version" = "$ALLURE_VERSION"
                '''
            }
        }

        stage('Compile tests') {
            steps {
                script {
                    try {
                        sh './gradlew testClasses --console=plain'
                        env.COMPILE_OUTCOME = 'success'
                    } catch (error) {
                        env.COMPILE_OUTCOME = 'failure'
                        throw error
                    }
                }
            }
        }

        stage('Run UI tests') {
            steps {
                script {
                    try {
                        withCredentials([
                            string(credentialsId: 'selenoid-username', variable: 'SELENOID_USER'),
                            string(credentialsId: 'selenoid-password', variable: 'SELENOID_PASSWORD')
                        ]) {
                            sh '''
                                ./gradlew test --console=plain \\
                                  -DbaseUrl=https://github.com \\
                                  -Dbrowser=chrome \\
                                  -DbrowserSize=1920x1080 \\
                                  -Dheadless=true \\
                                  "-Dselenide.remote=https://${SELENOID_USER}:${SELENOID_PASSWORD}@selenoid.qa.guru/wd/hub" \\
                                  "-Dselenide.browserVersion=$BROWSER_VERSION"
                            '''
                        }
                        env.TEST_OUTCOME = 'success'
                    } catch (error) {
                        env.TEST_OUTCOME = 'failure'
                        throw error
                    }
                }
            }
        }
    }

    post {
        always {
            sh '''
                set +e
                if find build/allure-results -type f -name '*-result.json' -print -quit 2>/dev/null | grep -q .; then
                    "$ALLURE_BIN" generate build/allure-results --clean -o build/allure-report
                else
                    echo 'No Allure test results; report generation skipped'
                fi
            '''

            junit allowEmptyResults: true, testResults: 'build/test-results/test/**/*.xml'

            archiveArtifacts allowEmptyArchive: true,
                artifacts: 'build/test-results/test/**/*,build/reports/tests/test/**/*,build/allure-results/**/*,build/allure-report/**/*'

            script {
                def notificationStatus = currentBuild.currentResult.toLowerCase()
                def sendFlag = ''
                if (env.TELEGRAM_NOTIFICATIONS_ENABLED == 'true') {
                    sendFlag = '--send'
                }

                def command = """
                    python3 scripts/telegram_notify.py \\
                      --xml-dir build/test-results/test \\
                      --project '${env.JOB_NAME}' \\
                      --ci 'Jenkins' \\
                      --branch '${env.BRANCH_NAME ?: 'unknown'}' \\
                      --commit '${env.GIT_COMMIT ?: 'unknown'}' \\
                      --run-url '${env.BUILD_URL}' \\
                      --compile-outcome '${env.COMPILE_OUTCOME}' \\
                      --test-outcome '${env.TEST_OUTCOME}' \\
                      --job-status '${notificationStatus}' \\
                      ${sendFlag}
                """

                if (sh(returnStatus: true, script: 'command -v python3 >/dev/null 2>&1') != 0) {
                    echo 'Python 3 is not installed on this agent; Telegram notification skipped'
                } else if (env.TELEGRAM_NOTIFICATIONS_ENABLED == 'true') {
                    withCredentials([
                        string(credentialsId: 'telegram-bot-token', variable: 'TELEGRAM_BOT_TOKEN'),
                        string(credentialsId: 'telegram-chat-id', variable: 'TELEGRAM_CHAT_ID')
                    ]) {
                        def result = sh(returnStatus: true, script: command)
                        if (result != 0) {
                            echo 'Telegram notification failed; preserving the original build result'
                            if (currentBuild.currentResult == 'SUCCESS') {
                                currentBuild.result = 'UNSTABLE'
                            }
                        }
                    }
                } else {
                    sh command
                    echo 'Telegram sending is disabled; dry-run completed'
                }
            }
        }
    }
}
