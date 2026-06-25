import random

def main():
    target = random.randint(1, 100)
    print("I'm thinking of a number between 1 and 100.")
    while True:
        try:
            guess = int(input("Your guess: "))
            if guess < target:
                print("Too low!")
            elif guess > target:
                print("Too high!")
            else:
                print("Congratulations! You guessed it.")
                break
        except ValueError:
            print("Please enter a valid number.")

if __name__ == "__main__":
    main()
