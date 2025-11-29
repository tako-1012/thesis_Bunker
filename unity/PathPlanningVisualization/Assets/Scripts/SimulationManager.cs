using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// シミュレーション全体の統合管理
/// ROS2連携、可視化、UI制御の中心
/// </summary>
public class SimulationManager : MonoBehaviour
{
    [Header("Visualizers")]
    public TerrainVisualizer terrainVisualizer;
    public PathVisualizer pathVisualizer;
    public RobotController robotController;
    public CameraController cameraController;
    
    [Header("UI")]
    public UIController uiController;
    
    [Header("ROS2")]
    public bool useROS2 = false;
    // ROS2連携は後で実装
    
    private int currentScenarioId = 0;
    private bool isPlaying = false;
    
    void Start()
    {
        // 初期シナリオ読み込み
        LoadScenario(0);
    }
    
    public void LoadScenario(int scenarioId)
    {
        currentScenarioId = scenarioId;
        
        // TODO: シナリオデータを読み込み
        // 今はダミーデータで動作確認
        LoadDummyScenario();
        
        uiController.UpdateStatus($"Scenario {scenarioId} loaded");
    }
    
    void LoadDummyScenario()
    {
        // ダミーの障害物グリッド生成
        byte[,,] occupancy = GenerateDummyOccupancy();
        terrainVisualizer.SetOccupancyGrid(occupancy);
        
        // ダミーの経路生成
        List<Vector3> path = GenerateDummyPath();
        pathVisualizer.SetPath(path);
        
        // スタート・ゴール設定
        Vector3 start = path[0];
        Vector3 goal = path[path.Count - 1];
        pathVisualizer.SetStartGoal(start, goal);
        
        // カメラフォーカス
        cameraController.FocusOnTarget(start);
    }
    
    byte[,,] GenerateDummyOccupancy()
    {
        byte[,,] grid = new byte[100, 100, 30];
        
        // ランダムな障害物配置
        for (int i = 0; i < 200; i++)
        {
            int x = Random.Range(10, 90);
            int y = Random.Range(10, 90);
            int z = Random.Range(0, 10);
            
            for (int dx = 0; dx < 5; dx++)
            {
                for (int dy = 0; dy < 5; dy++)
                {
                    for (int dz = 0; dz < 3; dz++)
                    {
                        if (x + dx < 100 && y + dy < 100 && z + dz < 30)
                        {
                            grid[x + dx, y + dy, z + dz] = 1;
                        }
                    }
                }
            }
        }
        
        return grid;
    }
    
    List<Vector3> GenerateDummyPath()
    {
        List<Vector3> path = new List<Vector3>();
        
        // ジグザグ経路
        for (int i = 0; i <= 20; i++)
        {
            float x = i * 0.4f;
            float y = Mathf.Sin(i * 0.5f) * 2f + 5f;
            float z = Mathf.Cos(i * 0.3f) * 0.5f + 0.5f;
            
            path.Add(new Vector3(x, z, y));
        }
        
        return path;
    }
    
    public void PlaySimulation()
    {
        if (isPlaying) return;
        
        isPlaying = true;
        
        // ロボット移動開始
        List<Vector3> path = pathVisualizer.GetPathPoints();
        robotController.FollowPath(path);
    }
    
    public void PauseSimulation()
    {
        isPlaying = false;
        Time.timeScale = 0f;
    }
    
    public void ResetSimulation()
    {
        isPlaying = false;
        Time.timeScale = 1f;
        robotController.ResetRobot();
        LoadScenario(currentScenarioId);
    }
    
    public void ToggleObstacles(bool show)
    {
        terrainVisualizer.ToggleObstacles(show);
    }
    
    public void ToggleWaypoints(bool show)
    {
        pathVisualizer.ToggleWaypoints(show);
    }
    
    public void ToggleTrail(bool show)
    {
        // Robot trail toggle
        robotController.showTrail = show;
    }
}


