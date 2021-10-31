# we use a "stable" Python version 3.9.x as 3.10 have just born
FROM python:3.9-alpine AS base

ENV CRONTAB_15MIN='*/15 * * * *' \
    CRONTAB_HOURLY='0 * * * *' \
    CRONTAB_DAILY='0 2 * * MON-SAT' \
    CRONTAB_WEEKLY='0 1 * * SUN' \
    CRONTAB_MONTHLY='0 5 1 * *' \
    DBS_TO_EXCLUDE='$^' \
    DST='' \
    EMAIL_FROM='' \
    EMAIL_SUBJECT='Backup report: {hostname} - {periodicity} - {result}' \
    EMAIL_TO='' \
    JOB_300_WHAT='dup \$SRC \$DST' \
    JOB_300_WHEN='daily' \
    OPTIONS='' \
    OPTIONS_EXTRA='--metadata-sync-mode partial' \
    SMTP_HOST='smtp' \
    SMTP_PASS='' \
    SMTP_PORT='25' \
    SMTP_TLS='' \
    SMTP_USER='' \
    SRC='/mnt/backup/src' \
    EXIT_ON_ERROR='false'

ENTRYPOINT [ "/usr/local/bin/entrypoint" ]
CMD ["/usr/sbin/crond", "-fd8"]

# Link the job runner in all periodicities available. Do all this on the same
# command to not generate extra layers
RUN ln -s /usr/local/bin/jobrunner /etc/periodic/15min/jobrunner; \
    ln -s /usr/local/bin/jobrunner /etc/periodic/hourly/jobrunner; \
    ln -s /usr/local/bin/jobrunner /etc/periodic/daily/jobrunner; \
    ln -s /usr/local/bin/jobrunner /etc/periodic/weekly/jobrunner; \
    ln -s /usr/local/bin/jobrunner /etc/periodic/monthly/jobrunner

# Runtime dependencies and database clients
RUN set -e; apk add --no-cache \
        ca-certificates \
        dbus \
        gettext \
        gnupg \
        krb5-libs \
        lftp \
        libffi \
        librsync \
        ncftp \
        openssh \
        openssl \
        rsync \
        tzdata \
    && sync

# Default backup source directory
RUN mkdir -p "$SRC"

# Preserve cache among containers
VOLUME [ "/root" ]

# Build dependencies
ADD requirements.txt requirements.txt
RUN set -e; apk add --no-cache --virtual .build \
        build-base \
        krb5-dev \
        libffi-dev \
        librsync-dev \
        libxml2-dev \
        libxslt-dev \
        openssl-dev \
        cargo \
    # Runtime dependencies, based on https://gitlab.com/duplicity/duplicity/-/blob/master/requirements.txt
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build \
    && rm -rf /root/.cargo

COPY bin/* /usr/local/bin/
COPY templates/* /usr/local/share/templates/
RUN chmod a+rx /usr/local/bin/* && sync

FROM base AS s3
ENV JOB_500_WHAT='dup full $SRC $DST' \
    JOB_500_WHEN='weekly' \
    OPTIONS_EXTRA='--metadata-sync-mode partial --full-if-older-than 1W --file-prefix-archive archive-$(hostname -f)- --file-prefix-manifest manifest-$(hostname -f)- --file-prefix-signature signature-$(hostname -f)- --s3-european-buckets --s3-multipart-chunk-size 10 --s3-use-new-style'


FROM base AS docker
RUN apk add --no-cache docker-cli


FROM docker AS docker-s3
ENV JOB_500_WHAT='dup full $SRC $DST' \
    JOB_500_WHEN='weekly' \
    OPTIONS_EXTRA='--metadata-sync-mode partial --full-if-older-than 1W --file-prefix-archive archive-$(hostname -f)- --file-prefix-manifest manifest-$(hostname -f)- --file-prefix-signature signature-$(hostname -f)- --s3-european-buckets --s3-multipart-chunk-size 10 --s3-use-new-style'


FROM base AS postgres

RUN set -e; apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/v3.13/main postgresql-client \
	&& psql --version \
    && pg_dump --version

# Install full version of grep to support more options
RUN apk add --no-cache grep

ENV JOB_200_WHAT set -euo pipefail; psql -0Atd postgres -c \"SELECT datname FROM pg_database WHERE NOT datistemplate AND datname != \'postgres\'\" | grep --null-data --invert-match -E \"\$DBS_TO_EXCLUDE\" | xargs -0tI DB pg_dump --dbname DB --no-owner --no-privileges --file \"\$SRC/DB.sql\"
ENV JOB_200_WHEN='daily weekly' \
    PGHOST=db


FROM postgres AS postgres-s3
ENV JOB_500_WHAT='dup full $SRC $DST' \
    JOB_500_WHEN='weekly' \
    OPTIONS_EXTRA='--metadata-sync-mode partial --full-if-older-than 1W --file-prefix-archive archive-$(hostname -f)- --file-prefix-manifest manifest-$(hostname -f)- --file-prefix-signature signature-$(hostname -f)- --s3-european-buckets --s3-multipart-chunk-size 10 --s3-use-new-style'


FROM base AS mysql

RUN set -e; apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/v3.13/main mariadb-client \
    && mysql --version \
    && mysqldump --version

# Install full version of grep to support more options
RUN set -e; apk add --no-cache grep
ENV JOB_200_WHAT set -euo pipefail; mysql -u\${MYSQL_USER} -p\${MYSQL_PASSWD} -h\${MYSQL_HOST} -srNe \"SHOW DATABASES\" | grep -Ev \"^(mysql|performance_schema|information_schema)\$\" | grep -Ev \"\$DBS_TO_EXCLUDE\" | xargs -tI DB mysqldump -u\${MYSQL_USER} -p\${MYSQL_PASSWD} -h\${MYSQL_HOST} --opt --result-file="\${SRC}/DB" DB
ENV JOB_200_WHEN='daily weekly' \
    MYSQL_HOST=db \
    MYSQL_USER=root \
    MYSQL_PASSWD=invalid


FROM mysql AS mysql-s3
ENV JOB_500_WHAT='dup full $SRC $DST' \
    JOB_500_WHEN='weekly' \
    OPTIONS_EXTRA='--metadata-sync-mode partial --full-if-older-than 1W --file-prefix-archive archive-$(hostname -f)- --file-prefix-manifest manifest-$(hostname -f)- --file-prefix-signature signature-$(hostname -f)- --s3-european-buckets --s3-multipart-chunk-size 10 --s3-use-new-style'


# Define Nextcloud Docker images. Actually, only PostgreSQL and MySQL (MariaDB)
# are supported. For SQL support, just use the base image and tweak-it to your
# needs
FROM postgres AS nextcloud-postgres

# First, install the "gosu" binary as Nextcloud requires running some commands as
# the HTTP user for keeping correct permissions and else. In addition, we install
# PHP CLI for interacting with the command
RUN set -e; apk add --no-cache gosu php7-cli \
    php7-intl \
    php7-openssl \
    php7-dba \
    php7-sqlite3 \
    php7-pear \
    php7-tokenizer \
    php7-phpdbg \
    php7-litespeed \
    php7-gmp \
    php7-pdo_mysql \
    php7-sodium \
    php7-pcntl \
    php7-common \
    php7-xsl \
    php7-fpm \
    php7-mysqlnd \
    php7-enchant \
    php7-pspell \
    php7-snmp \
    php7-doc \
    php7-fileinfo \
    php7-mbstring \
    php7-xmlrpc \
    php7-xmlreader \
    php7-pdo_sqlite \
    php7-exif \
    php7-opcache \
    php7-ldap \
    php7-posix \
    php7-session \
    php7-gd \
    php7-gettext \
    php7-json \
    php7-xml \
    php7-iconv \
    php7-sysvshm \
    php7-curl \
    php7-shmop \
    php7-odbc \
    php7-phar \
    php7-pdo_pgsql \
    php7-imap \
    php7-pdo_dblib \
    php7-pgsql \
    php7-pdo_odbc \
    php7-zip \
    php7-apache2 \
    php7-cgi \
    php7-ctype \
    php7-bcmath \
    php7-calendar \
    php7-tidy \
    php7 \
    php7-dom \
    php7-sockets \
    php7-dbg \
    php7-soap \
    php7-sysvmsg \
    php7-ffi \
    php7-embed \
    php7-ftp \
    php7-sysvsem \
    php7-pdo \
    php7-static \
    php7-bz2 \
    php7-mysqli \
    php7-simplexml \
    php7-xmlwriter \
    # verify that the binary works
    && su-exec nobody true

# define a "higher" priority to this job as it will set our Nextcloud instance
# in maintenance mode. The execution order is the following:
# │
# ├─ JOB_100 -> set Nextcloud into maintenance mode
# ├─ JOB_200 -> make a PostgreSQL copy for the Nextcloud database
# ├─ JOB_300 -> make an entire copy of the Nextcloud installation
# └─ JOB_600 -> remove Nextcloud from maintenance mode
ENV JOB_100_WHAT set -eu; maintenance-mode on
ENV JOB_100_WHEN="daily weekly"

ENV JOB_200_WHAT set -eu; pg_dump --dbname \${NEXTCLOUD_DB} --no-owner --no-privileges --file \"\${NEXTCLOUD_DB_DIR}/\${NEXTCLOUD_DB}.sql\"
ENV JOB_200_WHEN='daily weekly' \
    PGHOST=db

ENV JOB_600_WHAT set -eu; maintenance-mode off
ENV JOB_600_WHEN="daily weekly"

ENV NEXTCLOUD_DATA_DIR="$SRC/nextcloud/data" \
    NEXTCLOUD_HTTP_DIR="$SRC/nextcloud/www" \
    NEXTCLOUD_DB_DIR="$SRC/nextcloud"


FROM nextcloud-postgres AS nextcloud-postgres-s3
ENV JOB_500_WHAT='dup full $SRC $DST' \
    JOB_500_WHEN='weekly' \
    OPTIONS_EXTRA='--metadata-sync-mode partial --full-if-older-than 1W --file-prefix-archive archive-$(hostname -f)- --file-prefix-manifest manifest-$(hostname -f)- --file-prefix-signature signature-$(hostname -f)- --s3-european-buckets --s3-multipart-chunk-size 10 --s3-use-new-style'


FROM mysql AS nextcloud-mysql

# First, install the "gosu" binary as Nextcloud requires running some commands as
# the HTTP user for keeping correct permissions and else. In addition, we install
# PHP CLI for interacting with the command
RUN set -e; apk add --no-cache gosu php7-cli \
    php7-apcu \
    php7-redis \
    php7-intl \
    php7-openssl \
    php7-dba \
    php7-sqlite3 \
    php7-pear \
    php7-tokenizer \
    php7-phpdbg \
    php7-litespeed \
    php7-gmp \
    php7-pdo_mysql \
    php7-sodium \
    php7-pcntl \
    php7-common \
    php7-xsl \
    php7-fpm \
    php7-mysqlnd \
    php7-enchant \
    php7-pspell \
    php7-snmp \
    php7-doc \
    php7-fileinfo \
    php7-mbstring \
    php7-xmlrpc \
    php7-xmlreader \
    php7-pdo_sqlite \
    php7-exif \
    php7-opcache \
    php7-ldap \
    php7-posix \
    php7-session \
    php7-gd \
    php7-gettext \
    php7-json \
    php7-xml \
    php7-iconv \
    php7-sysvshm \
    php7-curl \
    php7-shmop \
    php7-odbc \
    php7-phar \
    php7-pdo_pgsql \
    php7-imap \
    php7-pdo_dblib \
    php7-pgsql \
    php7-pdo_odbc \
    php7-zip \
    php7-apache2 \
    php7-cgi \
    php7-ctype \
    php7-bcmath \
    php7-calendar \
    php7-tidy \
    php7 \
    php7-dom \
    php7-sockets \
    php7-dbg \
    php7-soap \
    php7-sysvmsg \
    php7-ffi \
    php7-embed \
    php7-ftp \
    php7-sysvsem \
    php7-pdo \
    php7-static \
    php7-bz2 \
    php7-mysqli \
    php7-simplexml \
    php7-xmlwriter \
    # verify that the binary works
    && su-exec nobody true

# define a "higher" priority to this job as it will set our Nextcloud instance
# in maintenance mode. The execution order is the following:
# │
# ├─ JOB_100 -> set Nextcloud into maintenance mode
# ├─ JOB_200 -> make a PostgreSQL copy for the Nextcloud database
# ├─ JOB_300 -> make an entire copy of the Nextcloud installation
# └─ JOB_600 -> remove Nextcloud from maintenance mode
ENV JOB_100_WHAT set -eu; maintenance-mode on
ENV JOB_100_WHEN="daily weekly"

ENV JOB_200_WHAT set -eu; mysqldump -u\${MYSQL_USER} -p\${MYSQL_PASSWD} -h\${MYSQL_HOST} --opt --result-file="\${NEXTCLOUD_DB_DIR}/\${NEXTCLOUD_DB}" \${NEXTCLOUD_DB}
ENV JOB_200_WHEN='daily weekly' \
    PGHOST=db

ENV JOB_600_WHAT set -eu; maintenance-mode off
ENV JOB_600_WHEN="daily weekly"

ENV NEXTCLOUD_DATA_DIR="$SRC/nextcloud/data" \
    NEXTCLOUD_HTTP_DIR="$SRC/nextcloud/www" \
    NEXTCLOUD_DB_DIR="$SRC/nextcloud"


FROM nextcloud-mysql AS nextcloud-mysql-s3
ENV JOB_500_WHAT='dup full $SRC $DST' \
    JOB_500_WHEN='weekly' \
    OPTIONS_EXTRA='--metadata-sync-mode partial --full-if-older-than 1W --file-prefix-archive archive-$(hostname -f)- --file-prefix-manifest manifest-$(hostname -f)- --file-prefix-signature signature-$(hostname -f)- --s3-european-buckets --s3-multipart-chunk-size 10 --s3-use-new-style'
