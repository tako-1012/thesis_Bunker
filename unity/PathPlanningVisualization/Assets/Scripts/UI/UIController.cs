using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// UI制御システム
/// シナリオ選択、再生制御、表示設定
/// </summary>
public class UIController : MonoBehaviour
{
    [Header("References")]
    public SimulationManager simulationManager;
    
    [Header("UI Elements")]
    public TMP_Dropdown scenarioDropdown;
    public Button playButton;
    public Button pauseButton;
    public Button resetButton;
    public Toggle obstaclesToggle;
    public Toggle waypointsToggle;
    public Toggle trailToggle;
    public TextMeshProUGUI statusText;
    public TextMeshProUGUI statsText;
    
    void Start()
    {
        InitializeUI();
        SetupCallbacks();
    }
    
    void InitializeUI()
    {
        // シナリオドロップダウンに項目追加
        scenarioDropdown.ClearOptions();
        
        var options = new System.Collections.Generic.List<string>();
        for (int i = 0; i < 100; i++)
        {
            options.Add($"Scenario {i:000}");
        }
        scenarioDropdown.AddOptions(options);
    }
    
    void SetupCallbacks()
    {
        playButton.onClick.AddListener(OnPlayClicked);
        pauseButton.onClick.AddListener(OnPauseClicked);
        resetButton.onClick.AddListener(OnResetClicked);
        
        obstaclesToggle.onValueChanged.AddListener(OnObstaclesToggled);
        waypointsToggle.onValueChanged.AddListener(OnWaypointsToggled);
        trailToggle.onValueChanged.AddListener(OnTrailToggled);
        
        scenarioDropdown.onValueChanged.AddListener(OnScenarioChanged);
    }
    
    void OnPlayClicked()
    {
        simulationManager.PlaySimulation();
        UpdateStatus("Playing...");
    }
    
    void OnPauseClicked()
    {
        simulationManager.PauseSimulation();
        UpdateStatus("Paused");
    }
    
    void OnResetClicked()
    {
        simulationManager.ResetSimulation();
        UpdateStatus("Reset");
    }
    
    void OnObstaclesToggled(bool value)
    {
        simulationManager.ToggleObstacles(value);
    }
    
    void OnWaypointsToggled(bool value)
    {
        simulationManager.ToggleWaypoints(value);
    }
    
    void OnTrailToggled(bool value)
    {
        simulationManager.ToggleTrail(value);
    }
    
    void OnScenarioChanged(int index)
    {
        simulationManager.LoadScenario(index);
        UpdateStatus($"Loaded Scenario {index:000}");
    }
    
    public void UpdateStatus(string message)
    {
        statusText.text = $"Status: {message}";
    }
    
    public void UpdateStats(string stats)
    {
        statsText.text = stats;
    }
}


