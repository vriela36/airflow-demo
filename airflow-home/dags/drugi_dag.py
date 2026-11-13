from airflow.sdk import dag, task

@dag(
    dag_id="drugi_dag",
    schedule=None,
    catchup=False,
)
def drugi_dag():
    @task
    def powitanie():
        print("Pierwsze zadanie działa!")

    @task
    def zakonczenie():
        print("Drugie zadanie działa!")

    powitanie() >> zakonczenie()


drugi_dag()