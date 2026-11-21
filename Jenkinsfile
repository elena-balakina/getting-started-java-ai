pipeline {
    agent {
        label 'java-jdk21'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
    }

    environment {
        CHROME_VERSION = '155.0.8059.84'
        ALLURE_VERSION = '2.46.1'
        ALLURE_SHA256 = '37428164f310c8d137cfdd2c3a25d049b233261ddab13e1bd4dfd7627b5cbf8d'
        TOOLS_DIR = "${WORKSPACE}/.ci-tools"
        CHROME_PATH = "${WORKSPACE}/.ci-tools/chrome-linux64/chrome"
        CHROMEDRIVER_PATH = "${WORKSPACE}/.ci-tools/chromedriver-linux64/chromedriver"
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

                    chrome_archive="$TOOLS_DIR/chrome-for-testing.zip"
                    chromedriver_archive="$TOOLS_DIR/chromedriver.zip"
                    allure_archive="$TOOLS_DIR/allure-commandline-$ALLURE_VERSION.tgz"

                    curl -fsSL -o "$chrome_archive" \
                      "https://storage.googleapis.com/chrome-for-testing-public/$CHROME_VERSION/linux64/chrome-linux64.zip"
                    curl -fsSL -o "$chromedriver_archive" \
                      "https://storage.googleapis.com/chrome-for-testing-public/$CHROME_VERSION/linux64/chromedriver-linux64.zip"
                    curl -fsSL -o "$allure_archive" \
                      "https://repo.maven.apache.org/maven2/io/qameta/allure/allure-commandline/$ALLURE_VERSION/allure-commandline-$ALLURE_VERSION.tgz"
                    echo "$ALLURE_SHA256  $allure_archive" | sha256sum --check --strict

                    rm -rf "$TOOLS_DIR/chrome-linux64" "$TOOLS_DIR/chromedriver-linux64" "$TOOLS_DIR/allure-$ALLURE_VERSION"
                    unzip -q -o "$chrome_archive" -d "$TOOLS_DIR"
                    unzip -q -o "$chromedriver_archive" -d "$TOOLS_DIR"
                    tar -xzf "$allure_archive" -C "$TOOLS_DIR"
                    chmod +x "$CHROME_PATH" "$CHROMEDRIVER_PATH" "$ALLURE_BIN"

                    "$CHROME_PATH" --version
                    "$CHROMEDRIVER_PATH" --version
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
                        sh '''
                            ./gradlew test --console=plain \\
                              -DbaseUrl=https://github.com \\
                              -Dbrowser=chrome \\
                              -DbrowserSize=1920x1080 \\
                              -Dheadless=true \\
                              "-Dselenide.browserBinary=$CHROME_PATH" \\
                              "-Dwebdriver.chrome.driver=$CHROMEDRIVER_PATH"
                        '''
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
                if compgen -G "build/allure-results/*-result.json" > /dev/null; then
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

                if (env.TELEGRAM_NOTIFICATIONS_ENABLED == 'true') {
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
