using UnityEngine;

/// <summary>
/// SceneController: シナリオの読み込み・地形/経路表示・カメラ調整・キー切替
/// </summary>
public class SceneController : MonoBehaviour
{
    [Header("Scenario Selection")]
    public string scenarioId = "demo_medium_moderate";

    [Header("Materials")]
    public Material terrainMaterial;
    public Material pathMaterial;

    private GameObject terrainParent;
    private GameObject pathParent;
    private TerrainVisualizer terrainVisualizer;
    private PathVisualizer pathVisualizer;

    void Start()
    {
        // Terrainオブジェクト生成
        terrainParent = new GameObject("Terrain");
        terrainVisualizer = terrainParent.AddComponent<TerrainVisualizer>();
        terrainVisualizer.terrainMaterial = terrainMaterial;

        // Pathオブジェクト生成
        pathParent = new GameObject("Paths");
        pathVisualizer = pathParent.AddComponent<PathVisualizer>();
        pathVisualizer.pathMaterial = pathMaterial;

        // シナリオ読み込み・表示
        LoadAndVisualize(scenarioId);
    }

    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Alpha1))
        {
            LoadAndVisualize("demo_small_moderate");
        }
        else if (Input.GetKeyDown(KeyCode.Alpha2))
        {
            LoadAndVisualize("demo_medium_moderate");
        }
        else if (Input.GetKeyDown(KeyCode.Alpha3))
        {
            LoadAndVisualize("demo_large_moderate");
        }
    }

    /// <summary>
    /// シナリオを読み込み、地形・経路を表示
    /// </summary>
    public void LoadAndVisualize(string scenarioId)
    {
        Debug.Log($"Loading scenario: {scenarioId}");
        ScenarioData data = DataLoader.LoadScenario(scenarioId);
        if (data == null)
        {
            Debug.LogError("Failed to load scenario data");
            return;
        }

        // 地形生成
        terrainVisualizer.GenerateTerrain(data.terrain);

        // 経路表示
        pathVisualizer.VisualizePaths(data.paths);

        // カメラ調整
        AdjustCamera(data.terrain);
    }

    /// <summary>
    /// カメラを地形中央・上方に配置
    /// </summary>
    private void AdjustCamera(TerrainData terrainData)
    {
        Camera mainCamera = Camera.main;
        if (mainCamera == null)
        {
            Debug.LogWarning("Main Camera not found");
            return;
        }
        if (terrainData == null || terrainData.gridSize == null || terrainData.gridSize.Count < 2)
        {
            Debug.LogWarning("Invalid terrain data for camera adjustment");
            return;
        }
        float centerX = terrainData.gridSize[0] * terrainData.resolution / 2f;
        float centerY = terrainData.gridSize[1] * terrainData.resolution / 2f;
        float height = Mathf.Max(terrainData.gridSize[0], terrainData.gridSize[1]) * terrainData.resolution * 1.2f;
        mainCamera.transform.position = new Vector3(centerX, centerY, height);
        mainCamera.transform.LookAt(new Vector3(centerX, centerY, 0));
    }
}
