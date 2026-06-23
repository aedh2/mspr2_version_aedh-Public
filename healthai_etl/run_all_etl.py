from etl_users import main as run_users
from etl_exercises import main as run_exercises
from etl_gym import main as run_gym
from etl_sleep import main as run_sleep
from etl_food import main as run_food
from post_etl_enrichment import main as run_post_enrichment
from etl_progression_photos import main as run_progression_photos


if __name__ == "__main__":
    run_users()
    run_exercises()
    run_gym()
    run_sleep()
    run_food()
    run_post_enrichment()
    run_progression_photos()
    print("Tous les ETL ont ete executes dans le bon ordre.")
