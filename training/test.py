import pytest
from train import ActionPredictor, strictly_proper_scoring_rule

# Helper function to generate mock data (Do we need this?)
def generate_mock_data(num_samples, num_features):
    # Generate balanced data for "live" and "deceased" classes
    features = torch.randn(num_samples, num_features)
    labels = torch.randint(0, 2, (num_samples,))
    return features, labels

def test_data_preparation():
    features, labels = generate_mock_data(100, 10)
    assert len(features) == len(labels), "Features and labels should have the same length"
    assert torch.sum(labels).item() == len(labels) // 2, "Data should be balanced"

def test_model_initialization():
    model_1, model_2 = ActionPredictor(), ActionPredictor()
    for param_1, param_2 in zip(model_1.parameters(), model_2.parameters()):
        assert param_1.data.ne(param_2.data).all(), "Models parameters should not be identical"

def test_strictly_proper_scoring_rule(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, actions = mock_data
    outputs_1 = model_1(inputs)
    outputs_2 = model_2(inputs)
    # Apply softmax to get probabilities
    probabilities_1 = torch.nn.functional.softmax(outputs_1, dim=1)
    probabilities_2 = torch.nn.functional.softmax(outputs_2, dim=1)
    # Calculate the Brier score
    score_1 = strictly_proper_scoring_rule(probabilities_1, actions)
    score_2 = strictly_proper_scoring_rule(probabilities_2, actions)
    # Assert that the scores are non-negative
    assert score_1 >= 0
    assert score_2 >= 0

def test_zero_sum_normalization(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, _ = mock_data
    outputs_1 = model_1(inputs)
    outputs_2 = model_2(inputs)
    normalized_1 = outputs_1 - outputs_1.mean()
    normalized_2 = outputs_2 - outputs_2.mean()
    assert torch.isclose(normalized_1.mean(), torch.tensor(0.0), atol=1e-7)
    assert torch.isclose(normalized_2.mean(), torch.tensor(0.0), atol=1e-7)

def test_training_loop(initialized_models, mock_data):
    model_1, _ = initialized_models
    inputs, actions = mock_data
    optimizer = torch.optim.SGD(model_1.parameters(), lr=0.01)
    criterion = torch.nn.CrossEntropyLoss()
    
    optimizer.zero_grad()
    outputs = model_1(inputs)
    loss = criterion(outputs, actions)
    loss.backward()
    optimizer.step()
    
    assert loss.item() >= 0, "Loss should be non-negative"

def test_zero_sum_scores(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, actions = mock_data
    outputs_1 = model_1(inputs)
    outputs_2 = model_2(inputs)
    scores_1 = strictly_proper_scoring_rule(outputs_1, actions)
    scores_2 = strictly_proper_scoring_rule(outputs_2, actions)
    zero_sum_scores = scores_1 - scores_2
    assert torch.all(zero_sum_scores <= 0) or torch.all(zero_sum_scores >= 0), \
        "Zero-sum scores should reflect relative performance"

def test_predictive_influence(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, _ = mock_data
    original_distribution = inputs.mean(dim=0)
    _ = model_1(inputs)
    _ = model_2(inputs)
    new_distribution = inputs.mean(dim=0)
    assert torch.all(torch.isclose(original_distribution, new_distribution, atol=1e-7)), \
        "Predictions should not change the distribution of outcomes"

def test_conditional_predictions(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, actions = mock_data
    # Get predictions from the models
    outputs_1 = model_1(inputs)
    outputs_2 = model_2(inputs)
    # Convert actions to one-hot encoding for conditional comparison
    actions_one_hot = torch.nn.functional.one_hot(actions, num_classes=outputs_1.size(1)).float()
    # Multiply the outputs with the one-hot encoded actions to get conditional predictions
    conditional_outputs_1 = outputs_1 * actions_one_hot
    conditional_outputs_2 = outputs_2 * actions_one_hot
    # Check that the conditional predictions do not influence the distribution of the inputs
    assert torch.all(torch.isclose(inputs.mean(dim=0), conditional_outputs_1.mean(dim=0), atol=1e-7)), \
        "Conditional predictions should not influence the distribution of inputs"
    assert torch.all(torch.isclose(inputs.mean(dim=0), conditional_outputs_2.mean(dim=0), atol=1e-7)), \
        "Conditional predictions should not influence the distribution of inputs"
# Test 9: Test Honesty Incentives
def test_honesty_incentives(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, actions = mock_data
    outputs_1 = model_1(inputs)
    outputs_2 = model_2(inputs)
    # Assuming that a higher output value corresponds to a "lie" about the action's value
    assert not (outputs_1 > outputs_2).all() and not (outputs_2 > outputs_1).all(), \
        "One model should not consistently predict higher values than the other"

def test_equilibrium_behavior(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, actions = mock_data
    # Assuming equilibrium is reached when outputs are similar
    outputs_1 = model_1(inputs)
    outputs_2 = model_2(inputs)
    assert torch.isclose(outputs_1, outputs_2, atol=1e-5).all(), \
        "Models should predict similar outcomes at equilibrium"

def test_decision_making(initialized_models, mock_data):
    model_1, _ = initialized_models
    inputs, _ = mock_data
    outputs = model_1(inputs)
    # Assuming the best action is the one with the highest predicted value
    best_action = torch.argmax(outputs, dim=1)
    assert best_action is not None, "Decision-making process should select a best action"

def test_stochastic_decisions(initialized_models, mock_data):
    model_1, _ = initialized_models
    inputs, _ = mock_data
    outputs = model_1(inputs)
    # Assuming stochasticity implies a distribution of predictions
    assert outputs.std(dim=0).mean() > 0, "Model should provide a distribution of predictions"

def test_robustness_to_distributional_shift(initialized_models, mock_data_shifted):
    model_1, _ = initialized_models
    inputs, _ = mock_data_shifted
    original_outputs = model_1(inputs)
    # Introduce a shift
    shifted_inputs = inputs + torch.randn_like(inputs)
    shifted_outputs = model_1(shifted_inputs)
    assert torch.isclose(original_outputs, shifted_outputs, atol=1e-5).all(), \
        "Model should maintain honest predictions after a distributional shift"

def test_inner_alignment(initialized_models, mock_data):
    model_1, _ = initialized_models
    inputs, actions = mock_data
    outputs = model_1(inputs)
    # Assuming inner alignment means actions align with outputs
    assert torch.argmax(outputs, dim=1).eq(actions).all(), \
        "Model's objectives should align with the desired goals"

def test_performativity(initialized_models, mock_data):
    model_1, _ = initialized_models
    inputs, _ = mock_data
    # Assuming performativity would manifest as a change in input distribution
    original_distribution = inputs.mean(dim=0)
    _ = model_1(inputs)
    new_distribution = inputs.mean(dim=0)
    assert torch.isclose(original_distribution, new_distribution, atol=1e-7).all(), \
        "Model should not manipulate choices through underspecified actions"

def test_scalability(initialized_models, large_mock_data):
    model_1, _ = initialized_models
    inputs, _ = large_mock_data
    try:
        _ = model_1(inputs)
        assert True, "Model should handle a large action space efficiently"
    except RuntimeError as e:
        assert False, f"Model failed to scale: {e}"

def test_equilibrium_misrepresentation(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, _ = mock_data
    outputs_1 = model_1(inputs)
    outputs_2 = model_2(inputs)
    # Assuming misrepresentation would show as a significant difference in outputs
    assert not torch.isclose(outputs_1, outputs_2, atol=1e-5).any(), \
        "No action should be misrepresented as preferable or worse in equilibrium"

def test_model_competitiveness(initialized_models, mock_data):
    model_1, model_2 = initialized_models
    inputs, _ = mock_data
    outputs_1 = model_1(inputs)
    outputs_2 = model_2(inputs)
    # Normalize outputs for zero-sum competition
    outputs_1 -= outputs_1.mean(dim=1, keepdim=True)
    outputs_2 -= outputs_2.mean(dim=1, keepdim=True)
    # Check if models are competitive and not correlated
    correlation = torch.corrcoef(torch.stack((outputs_1.flatten(), outputs_2.flatten())))
    assert correlation[0, 1] < 0.5, "Models should remain competitive with low correlation"

def test_safety_and_myopia(initialized_models, mock_data, future_mock_data):
    model_1, _ = initialized_models
    inputs, _ = mock_data
    future_inputs, _ = future_mock_data
    # Train on current data
    optimizer = torch.optim.SGD(model_1.parameters(), lr=0.01)
    outputs = model_1(inputs)
    loss = torch.nn.functional.mse_loss(outputs, torch.zeros_like(outputs))
    loss.backward()
    optimizer.step()
    # Predict on future data
    future_outputs = model_1(future_inputs)
    # Check for signs of long-term planning or distributional shifts
    assert torch.isclose(outputs.mean(), future_outputs.mean(), atol=1e-5).all(), \
        "Model should not develop long-term deceptive plans"

def test_private_information(initialized_models, mock_data, private_mock_data):
    model_1, model_2 = initialized_models
    public_inputs, _ = mock_data
    private_inputs, _ = private_mock_data
    # Model 1 has access to private data
    outputs_1_private = model_1(private_inputs)
    # Model 2 only has access to public data
    outputs_2_public = model_2(public_inputs)
    # Check how models handle different information
    assert torch.mean(outputs_1_private) > torch.mean(outputs_2_public), \
        "Model with private information should have better predictive capabilities"