from airflow.sdk import dag, task


@dag(
    dag_id="pierwszy_dag",
    schedule="*/5 * * * *",
    catchup=False,
)
def pierwszy_dag():

    @task
    def powitanie():
        print("Pierwsze zadanie działa!")

    @task
    def zakonczenie():
        print("Drugie zadanie działa!")

    @task
    def trzecie_zadanie():
        print("Trzecie zadanie działa!")

    powitanie() >> zakonczenie() >> trzecie_zadanie()


pierwszy_dag()