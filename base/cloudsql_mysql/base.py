from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper
from google.cloud.sql.connector import Connector


class DatabaseWrapper(MySQLDatabaseWrapper):
    """
    Uses the Cloud SQL Python Connector to open every new DB connection.
    """

    def get_new_connection(self, conn_params):
        instance_conn_name = self.settings_dict["OPTIONS"]["instance_connection_name"]
        ip_type = self.settings_dict["OPTIONS"].get("ip_type") or "public"
        enable_iam_auth = self.settings_dict["OPTIONS"].get("enable_iam_auth") or False
        refresh_strategy = self.settings_dict["OPTIONS"].get("refresh_strategy") or "background"
        connector = Connector(ip_type=ip_type, enable_iam_auth=enable_iam_auth, refresh_strategy=refresh_strategy)
        return connector.connect(
            instance_conn_name,
            "pymysql",
            user=conn_params["user"],
            db=conn_params["database"],
        )
