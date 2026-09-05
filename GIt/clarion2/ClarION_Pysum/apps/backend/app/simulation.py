import simpy
import random

class RFIPortfolioSimulation:
    def __init__(self, env: simpy.Environment, submission_rate: float):
        self.env = env
        self.submission_rate = submission_rate
        self.stats = {
            "total_submissions": 0, 
            "total_rfis": 0, 
            "delayed_submissions": 0,
            "total_days_simulated": 0
        }
        
    def submit_dossier(self):
        self.stats["total_submissions"] += 1
        
        # 30% chance of RFI (Validation or Assessment)
        if random.random() < 0.30:
            self.stats["total_rfis"] += 1
            
            # Simulated response time (in days)
            response_time = random.randint(5, 14)
            yield self.env.timeout(response_time)
            
            # SLA is typically 10 or 12 days. Let's say > 10 is delayed for this metric.
            if response_time > 10:
                self.stats["delayed_submissions"] += 1
        else:
            yield self.env.timeout(1)

    def run_submissions(self):
        while True:
            # Time until next submission (exponential distribution)
            yield self.env.timeout(random.expovariate(self.submission_rate))
            self.env.process(self.submit_dossier())

def run_simulation(days: int = 365, submission_rate: float = 650/365.0) -> dict:
    """
    Runs a SimPy simulation of RFI portfolio forecasting.
    By default, ~650 submissions a year across Europe.
    """
    env = simpy.Environment()
    sim = RFIPortfolioSimulation(env, submission_rate=submission_rate)
    env.process(sim.run_submissions())
    
    env.run(until=days)
    sim.stats["total_days_simulated"] = days
    
    return sim.stats

if __name__ == "__main__":
    results = run_simulation()
    print("Simulation Results:", results)
