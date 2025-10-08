using UnityEngine;
using System.Collections.Generic;
using System.Linq;

/// <summary>
/// Terrain World Manager for generating uneven terrain scenarios for 3D path planning research
/// Creates 5 different terrain scenarios: FlatWithObstacles, GentleSlope, SteepSlope, DenseObstacles, MixedTerrain
/// </summary>
public class TerrainWorldManager : MonoBehaviour
{
    [Header("Terrain Scenario Selection")]
    public TerrainScenario scenario = TerrainScenario.MixedTerrain;
    
    [Header("Terrain Generation Settings")]
    [Range(0.1f, 2.0f)]
    public float terrainSize = 1.0f;
    [Range(0.1f, 0.5f)]
    public float terrainResolution = 0.1f;
    [Range(1, 10)]
    public int terrainDetail = 5;
    
    [Header("Obstacle Settings")]
    public GameObject[] obstaclePrefabs;
    [Range(0, 100)]
    public int obstacleCount = 20;
    [Range(0.5f, 5.0f)]
    public float obstacleScaleMin = 1.0f;
    [Range(0.5f, 5.0f)]
    public float obstacleScaleMax = 2.0f;
    
    [Header("Start/Goal Points")]
    public Transform startPoint;
    public Transform goalPoint;
    public bool autoGenerateStartGoal = true;
    
    [Header("Debug Settings")]
    public bool showSlopeDebug = true;
    public bool showTerrainInfo = true;
    
    public enum TerrainScenario
    {
        FlatWithObstacles,    // 平坦地形+障害物
        GentleSlope,          // 緩傾斜地形（10-15度）
        SteepSlope,           // 急傾斜地形（20-30度）
        DenseObstacles,       // 障害物密集
        MixedTerrain          // 複合地形（最も現実的）
    }
    
    private Terrain terrain;
    private TerrainData terrainData;
    private List<GameObject> generatedObstacles = new List<GameObject>();
    private List<GameObject> generatedObjects = new List<GameObject>();
    
    // Terrain generation parameters
    private float[,] heightMap;
    private int terrainWidth;
    private int terrainLength;
    
    void Start()
    {
        Debug.Log("TerrainWorldManager: Starting terrain generation...");
        InitializeTerrain();
        GenerateTerrainScenario();
        Debug.Log("TerrainWorldManager: Terrain generation completed successfully!");
    }
    
    void InitializeTerrain()
    {
        try
        {
            Debug.Log("TerrainWorldManager: Initializing terrain...");
            
            // Create terrain object
            GameObject terrainObject = new GameObject("GeneratedTerrain");
            terrainObject.transform.SetParent(transform);
            
            // Add terrain component
            terrain = terrainObject.AddComponent<Terrain>();
            TerrainCollider terrainCollider = terrainObject.AddComponent<TerrainCollider>();
            
            // Create terrain data
            terrainData = ScriptableObject.CreateInstance<TerrainData>();
            terrainData.heightmapResolution = Mathf.RoundToInt(terrainSize / terrainResolution) + 1;
            terrainData.size = new Vector3(terrainSize * 100, 20, terrainSize * 100); // Scale up for realistic size
            
            terrainWidth = terrainData.heightmapResolution;
            terrainLength = terrainData.heightmapResolution;
            
            terrain.terrainData = terrainData;
            terrainCollider.terrainData = terrainData;
            
            Debug.Log($"TerrainWorldManager: Terrain initialized successfully - Resolution: {terrainWidth}x{terrainLength}, Size: {terrainData.size}");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"TerrainWorldManager: Failed to initialize terrain: {e.Message}");
            throw;
        }
    }
    
    void GenerateTerrainScenario()
    {
        try
        {
            Debug.Log($"TerrainWorldManager: Generating terrain scenario: {scenario}");
            
            // Clear previous generation
            ClearGeneratedObjects();
            
            // Generate height map based on scenario
            GenerateHeightMap();
            
            // Apply height map to terrain
            terrainData.SetHeights(0, 0, heightMap);
            
            // Generate obstacles based on scenario
            GenerateObstacles();
            
            // Set start and goal points
            SetStartGoalPoints();
            
            // Debug information
            if (showTerrainInfo)
            {
                AnalyzeTerrain();
            }
            
            Debug.Log($"TerrainWorldManager: Terrain scenario '{scenario}' generation completed successfully!");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"TerrainWorldManager: Failed to generate terrain scenario: {e.Message}");
            throw;
        }
    }
    
    void GenerateHeightMap()
    {
        heightMap = new float[terrainWidth, terrainLength];
        
        switch (scenario)
        {
            case TerrainScenario.FlatWithObstacles:
                GenerateFlatTerrain();
                break;
                
            case TerrainScenario.GentleSlope:
                GenerateGentleSlopeTerrain();
                break;
                
            case TerrainScenario.SteepSlope:
                GenerateSteepSlopeTerrain();
                break;
                
            case TerrainScenario.DenseObstacles:
                GenerateFlatTerrain(); // Start with flat, obstacles will be dense
                break;
                
            case TerrainScenario.MixedTerrain:
                GenerateMixedTerrain();
                break;
        }
        
        // Apply noise for natural variation
        ApplyPerlinNoise();
    }
    
    void GenerateFlatTerrain()
    {
        // Generate mostly flat terrain with slight variations
        for (int x = 0; x < terrainWidth; x++)
        {
            for (int z = 0; z < terrainLength; z++)
            {
                heightMap[x, z] = 0.1f + Random.Range(-0.05f, 0.05f);
            }
        }
    }
    
    void GenerateGentleSlopeTerrain()
    {
        // Generate gentle slopes (10-15 degrees)
        float maxSlope = 0.2f; // Approximately 15 degrees
        
        for (int x = 0; x < terrainWidth; x++)
        {
            for (int z = 0; z < terrainLength; z++)
            {
                // Create rolling hills
                float normalizedX = (float)x / terrainWidth;
                float normalizedZ = (float)z / terrainLength;
                
                float height = Mathf.Sin(normalizedX * Mathf.PI * 2) * Mathf.Cos(normalizedZ * Mathf.PI * 2) * maxSlope;
                height += Mathf.Sin(normalizedX * Mathf.PI * 4) * Mathf.Cos(normalizedZ * Mathf.PI * 4) * maxSlope * 0.5f;
                
                heightMap[x, z] = Mathf.Clamp(height + 0.2f, 0.1f, 0.4f);
            }
        }
    }
    
    void GenerateSteepSlopeTerrain()
    {
        // Generate steep slopes (20-30 degrees)
        float maxSlope = 0.4f; // Approximately 30 degrees
        
        for (int x = 0; x < terrainWidth; x++)
        {
            for (int z = 0; z < terrainLength; z++)
            {
                // Create steep hills and valleys
                float normalizedX = (float)x / terrainWidth;
                float normalizedZ = (float)z / terrainLength;
                
                float height = Mathf.Sin(normalizedX * Mathf.PI * 1.5f) * maxSlope;
                height += Mathf.Cos(normalizedZ * Mathf.PI * 1.5f) * maxSlope * 0.7f;
                
                heightMap[x, z] = Mathf.Clamp(height + 0.3f, 0.1f, 0.6f);
            }
        }
    }
    
    void GenerateMixedTerrain()
    {
        // Generate complex terrain with various slopes and features
        for (int x = 0; x < terrainWidth; x++)
        {
            for (int z = 0; z < terrainLength; z++)
            {
                float normalizedX = (float)x / terrainWidth;
                float normalizedZ = (float)z / terrainLength;
                
                // Multiple frequency components for complex terrain
                float height = 0f;
                
                // Large scale features
                height += Mathf.Sin(normalizedX * Mathf.PI * 1.2f) * Mathf.Cos(normalizedZ * Mathf.PI * 1.2f) * 0.3f;
                
                // Medium scale features
                height += Mathf.Sin(normalizedX * Mathf.PI * 3f) * Mathf.Cos(normalizedZ * Mathf.PI * 3f) * 0.15f;
                
                // Small scale features
                height += Mathf.Sin(normalizedX * Mathf.PI * 6f) * Mathf.Cos(normalizedZ * Mathf.PI * 6f) * 0.08f;
                
                // Add some ridges and valleys
                if (normalizedX > 0.3f && normalizedX < 0.7f)
                {
                    height += Mathf.Sin((normalizedX - 0.3f) * Mathf.PI * 2.5f) * 0.2f;
                }
                
                heightMap[x, z] = Mathf.Clamp(height + 0.25f, 0.1f, 0.5f);
            }
        }
    }
    
    void ApplyPerlinNoise()
    {
        // Add natural variation using Perlin noise
        float noiseScale = 0.1f;
        
        for (int x = 0; x < terrainWidth; x++)
        {
            for (int z = 0; z < terrainLength; z++)
            {
                float noise = Mathf.PerlinNoise(x * noiseScale, z * noiseScale) * 0.05f;
                heightMap[x, z] += noise;
                heightMap[x, z] = Mathf.Clamp(heightMap[x, z], 0.05f, 0.7f);
            }
        }
    }
    
    void GenerateObstacles()
    {
        int obstaclesToGenerate = obstacleCount;
        
        // Adjust obstacle count based on scenario
        switch (scenario)
        {
            case TerrainScenario.FlatWithObstacles:
                obstaclesToGenerate = obstacleCount;
                break;
                
            case TerrainScenario.GentleSlope:
                obstaclesToGenerate = Mathf.RoundToInt(obstacleCount * 0.6f);
                break;
                
            case TerrainScenario.SteepSlope:
                obstaclesToGenerate = Mathf.RoundToInt(obstacleCount * 0.3f);
                break;
                
            case TerrainScenario.DenseObstacles:
                obstaclesToGenerate = obstacleCount * 2;
                break;
                
            case TerrainScenario.MixedTerrain:
                obstaclesToGenerate = obstacleCount;
                break;
        }
        
        // Generate obstacles
        for (int i = 0; i < obstaclesToGenerate; i++)
        {
            GenerateSingleObstacle();
        }
        
        Debug.Log($"Generated {obstaclesToGenerate} obstacles for scenario: {scenario}");
    }
    
    void GenerateSingleObstacle()
    {
        // Random position within terrain bounds
        Vector3 terrainSize = terrainData.size;
        Vector3 randomPos = new Vector3(
            Random.Range(-terrainSize.x * 0.4f, terrainSize.x * 0.4f),
            0f,
            Random.Range(-terrainSize.z * 0.4f, terrainSize.z * 0.4f)
        );
        
        // Get height at position
        float height = terrain.SampleHeight(randomPos);
        randomPos.y = height;
        
        // Create obstacle
        GameObject obstacle;
        if (obstaclePrefabs != null && obstaclePrefabs.Length > 0)
        {
            // Use prefab if available
            GameObject prefab = obstaclePrefabs[Random.Range(0, obstaclePrefabs.Length)];
            obstacle = Instantiate(prefab, randomPos, Quaternion.identity);
        }
        else
        {
            // Create primitive obstacle
            obstacle = CreatePrimitiveObstacle(randomPos);
        }
        
        // Random scale
        float scale = Random.Range(obstacleScaleMin, obstacleScaleMax);
        obstacle.transform.localScale = Vector3.one * scale;
        
        // Random rotation
        obstacle.transform.rotation = Quaternion.Euler(0, Random.Range(0, 360), 0);
        
        obstacle.transform.SetParent(transform);
        obstacle.tag = "Obstacle";
        obstacle.name = $"Obstacle_{generatedObstacles.Count}";
        
        generatedObstacles.Add(obstacle);
    }
    
    GameObject CreatePrimitiveObstacle(Vector3 position)
    {
        GameObject obstacle;
        
        // Random obstacle type
        int obstacleType = Random.Range(0, 3);
        switch (obstacleType)
        {
            case 0: // Rock
                obstacle = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                break;
            case 1: // Log
                obstacle = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                break;
            case 2: // Tree trunk
                obstacle = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                break;
            default:
                obstacle = GameObject.CreatePrimitive(PrimitiveType.Cube);
                break;
        }
        
        obstacle.transform.position = position;
        
        // Set material color
        Renderer renderer = obstacle.GetComponent<Renderer>();
        Material material = new Material(Shader.Find("Standard"));
        
        switch (obstacleType)
        {
            case 0: // Rock - gray
                material.color = new Color(0.5f, 0.5f, 0.5f);
                break;
            case 1: // Log - brown
                material.color = new Color(0.6f, 0.4f, 0.2f);
                break;
            case 2: // Tree - dark green
                material.color = new Color(0.2f, 0.4f, 0.2f);
                break;
        }
        
        renderer.material = material;
        
        return obstacle;
    }
    
    void SetStartGoalPoints()
    {
        if (!autoGenerateStartGoal) return;
        
        Vector3 terrainSize = terrainData.size;
        
        // Generate start point (safe area)
        Vector3 startPos = new Vector3(
            Random.Range(-terrainSize.x * 0.3f, terrainSize.x * 0.3f),
            0f,
            Random.Range(-terrainSize.z * 0.3f, terrainSize.z * 0.3f)
        );
        startPos.y = terrain.SampleHeight(startPos) + 1f;
        
        // Generate goal point (opposite side)
        Vector3 goalPos = new Vector3(
            Random.Range(-terrainSize.x * 0.3f, terrainSize.x * 0.3f),
            0f,
            Random.Range(-terrainSize.z * 0.3f, terrainSize.z * 0.3f)
        );
        goalPos.y = terrain.SampleHeight(goalPos) + 1f;
        
        // Create start point
        if (startPoint == null)
        {
            GameObject startObj = new GameObject("StartPoint");
            startObj.transform.position = startPos;
            startObj.transform.SetParent(transform);
            startPoint = startObj.transform;
        }
        else
        {
            startPoint.position = startPos;
        }
        
        // Create goal point
        if (goalPoint == null)
        {
            GameObject goalObj = new GameObject("GoalPoint");
            goalObj.transform.position = goalPos;
            goalObj.transform.SetParent(transform);
            goalPoint = goalObj.transform;
        }
        else
        {
            goalPoint.position = goalPos;
        }
        
        // Visual indicators
        CreatePointIndicator(startPoint, Color.green, "Start");
        CreatePointIndicator(goalPoint, Color.red, "Goal");
        
        Debug.Log($"Start point: {startPos}, Goal point: {goalPos}");
    }
    
    void CreatePointIndicator(Transform point, Color color, string label)
    {
        // Create visual indicator
        GameObject indicator = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        indicator.transform.SetParent(point);
        indicator.transform.localPosition = Vector3.zero;
        indicator.transform.localScale = new Vector3(2f, 0.1f, 2f);
        
        Renderer renderer = indicator.GetComponent<Renderer>();
        Material material = new Material(Shader.Find("Standard"));
        material.color = color;
        renderer.material = material;
        
        // Add label
        GameObject labelObj = new GameObject($"{label}Label");
        labelObj.transform.SetParent(point);
        labelObj.transform.localPosition = Vector3.up * 2f;
        
        // Note: In a real implementation, you might want to use TextMesh or UI Text
        // For now, we'll just use the GameObject name
    }
    
    void AnalyzeTerrain()
    {
        if (heightMap == null) return;
        
        float minHeight = float.MaxValue;
        float maxHeight = float.MinValue;
        float totalHeight = 0f;
        int sampleCount = 0;
        
        // Sample terrain heights
        for (int x = 0; x < terrainWidth; x += 10)
        {
            for (int z = 0; z < terrainLength; z += 10)
            {
                float height = heightMap[x, z];
                minHeight = Mathf.Min(minHeight, height);
                maxHeight = Mathf.Max(maxHeight, height);
                totalHeight += height;
                sampleCount++;
            }
        }
        
        float avgHeight = totalHeight / sampleCount;
        float heightRange = maxHeight - minHeight;
        
        Debug.Log($"Terrain Analysis - Scenario: {scenario}");
        Debug.Log($"Height Range: {minHeight:F3} to {maxHeight:F3} (Range: {heightRange:F3})");
        Debug.Log($"Average Height: {avgHeight:F3}");
        Debug.Log($"Obstacle Count: {generatedObstacles.Count}");
        
        if (showSlopeDebug)
        {
            AnalyzeSlopes();
        }
    }
    
    void AnalyzeSlopes()
    {
        int steepSlopes = 0;
        int moderateSlopes = 0;
        int gentleSlopes = 0;
        
        for (int x = 1; x < terrainWidth - 1; x += 5)
        {
            for (int z = 1; z < terrainLength - 1; z += 5)
            {
                // Calculate slope using height differences
                float heightCenter = heightMap[x, z];
                float heightRight = heightMap[x + 1, z];
                float heightForward = heightMap[x, z + 1];
                
                float slopeX = Mathf.Atan(Mathf.Abs(heightRight - heightCenter) / terrainResolution) * Mathf.Rad2Deg;
                float slopeZ = Mathf.Atan(Mathf.Abs(heightForward - heightCenter) / terrainResolution) * Mathf.Rad2Deg;
                float maxSlope = Mathf.Max(slopeX, slopeZ);
                
                if (maxSlope > 25f)
                    steepSlopes++;
                else if (maxSlope > 10f)
                    moderateSlopes++;
                else
                    gentleSlopes++;
            }
        }
        
        Debug.Log($"Slope Analysis - Steep (>25°): {steepSlopes}, Moderate (10-25°): {moderateSlopes}, Gentle (<10°): {gentleSlopes}");
    }
    
    void ClearGeneratedObjects()
    {
        try
        {
            Debug.Log("TerrainWorldManager: Clearing previously generated objects...");
            
            // Clear obstacles
            foreach (GameObject obj in generatedObstacles.ToList())
            {
                if (obj != null)
                {
                    if (Application.isPlaying)
                        Destroy(obj);
                    else
                        DestroyImmediate(obj);
                }
            }
            generatedObstacles.Clear();
            
            // Clear other generated objects
            foreach (GameObject obj in generatedObjects.ToList())
            {
                if (obj != null)
                {
                    if (Application.isPlaying)
                        Destroy(obj);
                    else
                        DestroyImmediate(obj);
                }
            }
            generatedObjects.Clear();
            
            // Clear tagged objects
            string[] tagsToClean = { "Obstacle", "Start", "Goal" };
            foreach (string tag in tagsToClean)
            {
                GameObject[] objects = GameObject.FindGameObjectsWithTag(tag);
                foreach (GameObject obj in objects)
                {
                    if (obj != null && obj.transform.IsChildOf(transform))
                    {
                        if (Application.isPlaying)
                            Destroy(obj);
                        else
                            DestroyImmediate(obj);
                    }
                }
            }
            
            Debug.Log("TerrainWorldManager: Object cleanup completed");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"TerrainWorldManager: Error during object cleanup: {e.Message}");
        }
    }
    
    [ContextMenu("Regenerate Terrain")]
    public void RegenerateTerrain()
    {
        Debug.Log("Regenerating terrain...");
        GenerateTerrainScenario();
    }
    
    [ContextMenu("Switch to Next Scenario")]
    public void SwitchToNextScenario()
    {
        int currentIndex = (int)scenario;
        int nextIndex = (currentIndex + 1) % System.Enum.GetValues(typeof(TerrainScenario)).Length;
        scenario = (TerrainScenario)nextIndex;
        
        Debug.Log($"Switching to scenario: {scenario}");
        GenerateTerrainScenario();
    }
    
    void OnDrawGizmos()
    {
        if (startPoint != null)
        {
            Gizmos.color = Color.green;
            Gizmos.DrawWireSphere(startPoint.position, 1f);
        }
        
        if (goalPoint != null)
        {
            Gizmos.color = Color.red;
            Gizmos.DrawWireSphere(goalPoint.position, 1f);
        }
    }
}

