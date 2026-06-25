import sys
import mpmath

def compute_pi(places):
    # Set the decimal places (add a few extra for safety during internal calculation)
    mpmath.mp.dps = places + 5 
    
    # Get pi as a string
    pi_str = str(mpmath.pi)
    
    # Extract exactly the required number of places
    # "3." takes up 2 characters, so we need places + 2 characters total
    result = pi_str[:places + 2]
    
    with open('pi_50000.txt', 'w') as f:
        f.write(result)
        
    print(f"Computed Pi to {places} decimal places and saved to 'pi_50000.txt'.")

if __name__ == "__main__":
    compute_pi(50000)
