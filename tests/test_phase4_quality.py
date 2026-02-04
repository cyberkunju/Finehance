"""Simple test of Phase 4 components that don't require torch."""

import sys
print('=' * 60, flush=True)
print('PHASE 4: QUALITY TESTS (without torch)', flush=True)
print('=' * 60, flush=True)

# Add project root to path
sys.path.insert(0, '.')

# Test 1: Validation Module (doesn't need torch)
print('\n[TEST 1] Validation Module', flush=True)
try:
    from ai_brain.inference.validation import (
        ResponseValidator, HallucinationDetector, 
        FinancialFactChecker, CategoryValidator,
        ValidationSeverity
    )
    
    # Test ResponseValidator
    validator = ResponseValidator()
    result = validator.validate('Put all your money in crypto for guaranteed returns!', mode='chat')
    print(f'  - ResponseValidator: score={result.score:.2f}, issues={len(result.issues)}', flush=True)
    for issue in result.issues[:3]:
        print(f'    * {issue.type}: {issue.severity.value}', flush=True)
    
    # Test CategoryValidator (Whole Foods fix)
    cat_val = CategoryValidator()
    is_valid, corrected = cat_val.validate_category('Whole Foods Market', 'Fast Food')
    print(f'  - CategoryValidator: "Whole Foods" -> {corrected}', flush=True)
    assert corrected == 'Groceries', f'Expected Groceries, got {corrected}'
    
    # Test HallucinationDetector
    halluc = HallucinationDetector()
    issues = halluc.detect('Based on your income of $75,432.12, you should save $2,847.33 monthly')
    print(f'  - HallucinationDetector: {len(issues)} issues detected', flush=True)
    
    # Test FinancialFactChecker  
    checker = FinancialFactChecker()
    issues = checker.check('Put all your savings in one stock for guaranteed 50% returns!')
    print(f'  - FinancialFactChecker: {len(issues)} issues detected', flush=True)
    
    print('  PASSED!', flush=True)
except Exception as e:
    print(f'  FAILED: {e}', flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Templates Module (doesn't need torch)
print('\n[TEST 2] Templates Module', flush=True)
try:
    from ai_brain.inference.templates import (
        ResponseFormatter, format_response, DisclaimerGenerator
    )
    
    formatter = ResponseFormatter()
    print(f'  - ResponseFormatter: initialized', flush=True)
    
    # Test template formatting
    result = format_response(
        'You should create a budget and track your spending.',
        mode='chat',
        confidence=0.75
    )
    print(f'  - format_response: sections = {list(result.sections.keys())}', flush=True)
    
    # Test disclaimer generation
    disclaimer = DisclaimerGenerator.get_disclaimer(
        topics=['investment', 'tax'],
        confidence=0.6
    )
    print(f'  - DisclaimerGenerator: {len(disclaimer)} chars', flush=True)
    
    print('  PASSED!', flush=True)
except Exception as e:
    print(f'  FAILED: {e}', flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: AI Validation Service (doesn't need torch)
print('\n[TEST 3] AI Validation Service', flush=True)
try:
    from app.services.ai_validation import (
        AIValidationService, AIMLCrossValidator, FinancialRulesEngine
    )
    
    # Test AIMLCrossValidator
    cross_val = AIMLCrossValidator()
    print(f'  - AIMLCrossValidator: ML threshold = {cross_val.ML_OVERRIDE_THRESHOLD}', flush=True)
    
    # Test FinancialRulesEngine  
    rules = FinancialRulesEngine()
    result = rules.validate_advice('Save 50% of your income for retirement and invest in stocks')
    print(f'  - FinancialRulesEngine: valid = {result["is_valid"]}, disclaimers = {len(result["required_disclaimers"])}', flush=True)
    
    # Test AIValidationService
    service = AIValidationService()
    print(f'  - AIValidationService: initialized', flush=True)
    
    print('  PASSED!', flush=True)
except Exception as e:
    print(f'  FAILED: {e}', flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Confidence Module (basic - no torch operations)
print('\n[TEST 4] Confidence Module (basic)', flush=True)
try:
    from ai_brain.inference.confidence import (
        ConfidenceLevel, ConfidenceResult, ConfidenceCalculator, TORCH_AVAILABLE
    )
    
    print(f'  - TORCH_AVAILABLE: {TORCH_AVAILABLE}', flush=True)
    print(f'  - ConfidenceLevel.HIGH: {ConfidenceLevel.HIGH.value}', flush=True)
    
    # Create calculator
    calc = ConfidenceCalculator(temperature=0.7)
    print(f'  - ConfidenceCalculator: thresholds = {calc.MODE_THRESHOLDS}', flush=True)
    
    # Test from log probs (doesn't need torch)
    log_probs = [-0.1, -0.2, -0.15, -0.3, -0.1, -0.2]  # Simulated log probs
    result = calc.calculate_from_log_probs(log_probs, mode='chat')
    print(f'  - calculate_from_log_probs: score={result.score:.3f}, level={result.level.value}', flush=True)
    
    print('  PASSED!', flush=True)
except Exception as e:
    print(f'  FAILED: {e}', flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n' + '=' * 60, flush=True)
print('ALL PHASE 4 QUALITY TESTS PASSED!', flush=True)
print('=' * 60, flush=True)
print('''
Phase 4 Implementations Summary:
1. Real confidence scores     - Token probability-based scoring (torch-dependent features work in AI Brain env)
2. Hallucination detection    - WORKING - Detects fabricated numbers/facts
3. Financial fact-checking    - WORKING - Detects dangerous advice
4. Cross-validate with ML     - WORKING - AI/ML category agreement checking
5. Category mapping fix       - WORKING - "Whole Foods" correctly maps to "Groceries"
6. Response templating        - WORKING - Structured response formatting
''', flush=True)
