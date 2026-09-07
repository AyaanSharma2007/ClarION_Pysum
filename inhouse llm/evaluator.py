import json
import os

class DeploymentRejectedError(Exception):
    pass

def fields_match(prediction, ground_truth):
    """
    Dummy match function. In reality, this would check if the JSON fields match.
    """
    try:
        pred_json = json.loads(prediction)
        return pred_json == ground_truth
    except Exception:
        return False

class Evaluator:
    def __init__(self, data_dir="."):
        self.test_file = os.path.join(data_dir, "clarion_extraction_test.jsonl")
        self.baseline_accuracy_file = os.path.join(data_dir, "baseline_accuracy.txt")

    def record_baseline(self, accuracy):
        with open(self.baseline_accuracy_file, "w") as f:
            f.write(str(accuracy))
        print(f"Step 0 Baseline accuracy recorded: {accuracy}")

    def get_baseline(self):
        if not os.path.exists(self.baseline_accuracy_file):
            raise Exception("Baseline accuracy not found. Step 0 must be run first.")
        with open(self.baseline_accuracy_file, "r") as f:
            return float(f.read().strip())

    def evaluate_extraction(self, extract_fn):
        """
        Step 5: Evaluate before deploying.
        Runs against the frozen clarion_extraction_test.jsonl.
        """
        if not os.path.exists(self.test_file):
            raise Exception("Test set not found. Must run Step 2 first.")

        with open(self.test_file, "r") as f:
            test_set = [json.loads(line) for line in f]

        correct = 0
        for example in test_set:
            prediction = extract_fn(example["input"])
            if fields_match(prediction, json.loads(example["output"])):
                correct += 1
        
        accuracy = correct / len(test_set) if len(test_set) > 0 else 0
        print(f"Evaluation completed. Accuracy: {accuracy}")
        return accuracy

    def check_guardrail_1(self, fine_tuned_accuracy):
        """
        Guardrail 1: Never deploy a fine-tune that doesn't beat the Step 0 baseline.
        """
        baseline_accuracy = self.get_baseline()
        print(f"Comparing Fine-tuned ({fine_tuned_accuracy}) to Baseline ({baseline_accuracy})")
        
        if fine_tuned_accuracy <= baseline_accuracy:
            raise DeploymentRejectedError(
                f"Guardrail 1 Violation: Fine-tuned model accuracy ({fine_tuned_accuracy}) "
                f"did not beat the baseline ({baseline_accuracy}). Deployment rejected."
            )
        print("Guardrail 1 Passed: Fine-tuned model beat the baseline.")
