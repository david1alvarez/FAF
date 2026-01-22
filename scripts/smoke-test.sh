#!/bin/bash
# Smoke test for FAF Map AI development environment
# Verifies all required dependencies are installed and accessible

set -e

PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    local expected_pattern="$3"

    if output=$($cmd 2>&1); then
        if echo "$output" | grep -qE "$expected_pattern"; then
            echo "[OK] $name: $(echo "$output" | head -1)"
            ((PASS++))
            return 0
        fi
    fi
    echo "[FAIL] $name"
    ((FAIL++))
    return 1
}

check_python_package() {
    local package="$1"
    local display_name="$2"

    if python -c "import $package" 2>/dev/null; then
        version=$(python -c "import $package; print(getattr($package, '__version__', 'installed'))" 2>/dev/null || echo "installed")
        echo "[OK] $display_name installed: $version"
        ((PASS++))
        return 0
    fi
    echo "[FAIL] $display_name not installed"
    ((FAIL++))
    return 1
}

check_workspace() {
    if [ -d "/workspace" ] && [ "$(pwd)" = "/workspace" ]; then
        echo "[OK] Workspace mounted at /workspace"
        ((PASS++))
        return 0
    fi
    echo "[FAIL] Workspace not mounted correctly"
    ((FAIL++))
    return 1
}

echo "=== FAF Map AI Smoke Test ==="
echo ""

# Check Java version (17+)
check "Java version" "java -version" "version \"(17|18|19|20|21|22)"

# Check Python version (3.11+)
check "Python version" "python --version" "Python 3\.(1[1-9]|[2-9][0-9])"

# Check Gradle version (8.x)
check "Gradle version" "gradle --version" "Gradle 8\."

# Check Python packages
check_python_package "torch" "PyTorch"
check_python_package "numpy" "NumPy"
check_python_package "PIL" "Pillow"

# Check workspace
check_workspace

echo ""
echo "=== Results ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [ $FAIL -gt 0 ]; then
    exit 1
fi

echo ""
echo "All checks passed!"
exit 0
