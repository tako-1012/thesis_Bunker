using UnityEngine;

/// <summary>
/// Master script to create a complete test world for Bunker robot simulation
/// This combines environment setup, obstacles, paths, and interactive elements
/// </summary>
public class TestWorldManager : MonoBehaviour
{
    [Header("World Components")]
    public bool setupEnvironment = true;
    public bool createObstacles = true;
    public bool createPath = true;
    public bool addInteractiveElements = true;
    
    [Header("World Presets")]
    public WorldPreset worldPreset = WorldPreset.NavigationTest;
    
    public enum WorldPreset
    {
        NavigationTest,
        ObstacleAvoidance,
        RaceTrack,
        OpenField,
        Urban
    }
    
    private EnvironmentSetup environmentSetup;
    private WorldBuilder worldBuilder;
    private PathCreator pathCreator;
    
    void Start()
    {
        CreateTestWorld();
    }
    
    void CreateTestWorld()
    {
        Debug.Log($"Creating test world with preset: {worldPreset}");
        
        // Setup components
        SetupComponents();
        
        // Configure based on preset
        ConfigureForPreset();
        
        // Build the world
        if (setupEnvironment && environmentSetup != null)
        {
            environmentSetup.SetupEnvironment();
        }
        
        if (createPath && pathCreator != null)
        {
            pathCreator.CreateCircularPath();
        }
        
        if (createObstacles && worldBuilder != null)
        {
            worldBuilder.BuildWorld();
        }
        
        if (addInteractiveElements)
        {
            AddInteractiveElements();
        }
        
        Debug.Log("Test world creation completed!");
    }
    
    void SetupComponents()
    {
        // Add or get required components
        environmentSetup = GetComponent<EnvironmentSetup>();
        if (environmentSetup == null && setupEnvironment)
        {
            environmentSetup = gameObject.AddComponent<EnvironmentSetup>();
        }
        
        worldBuilder = GetComponent<WorldBuilder>();
        if (worldBuilder == null && createObstacles)
        {
            worldBuilder = gameObject.AddComponent<WorldBuilder>();
        }
        
        pathCreator = GetComponent<PathCreator>();
        if (pathCreator == null && createPath)
        {
            pathCreator = gameObject.AddComponent<PathCreator>();
        }
    }
    
    void ConfigureForPreset()
    {
        switch (worldPreset)
        {
            case WorldPreset.NavigationTest:
                ConfigureNavigationTest();
                break;
                
            case WorldPreset.ObstacleAvoidance:
                ConfigureObstacleAvoidance();
                break;
                
            case WorldPreset.RaceTrack:
                ConfigureRaceTrack();
                break;
                
            case WorldPreset.OpenField:
                ConfigureOpenField();
                break;
                
            case WorldPreset.Urban:
                ConfigureUrban();
                break;
        }
    }
    
    void ConfigureNavigationTest()
    {
        if (worldBuilder != null)
        {
            worldBuilder.obstacleCount = 8;
            worldBuilder.buildingCount = 3;
        }
        
        if (pathCreator != null)
        {
            pathCreator.pathRadius = 15f;
            pathCreator.pathPoints = 16;
            pathCreator.createWaypoints = true;
        }
    }
    
    void ConfigureObstacleAvoidance()
    {
        if (worldBuilder != null)
        {
            worldBuilder.obstacleCount = 20;
            worldBuilder.buildingCount = 1;
        }
        
        createPath = false;
    }
    
    void ConfigureRaceTrack()
    {
        if (pathCreator != null)
        {
            pathCreator.pathRadius = 25f;
            pathCreator.pathPoints = 24;
            pathCreator.pathWidth = 4f;
            pathCreator.createWaypoints = true;
        }
        
        if (worldBuilder != null)
        {
            worldBuilder.obstacleCount = 5;
            worldBuilder.buildingCount = 8;
        }
    }
    
    void ConfigureOpenField()
    {
        if (worldBuilder != null)
        {
            worldBuilder.obstacleCount = 3;
            worldBuilder.buildingCount = 0;
        }
        
        if (environmentSetup != null)
        {
            environmentSetup.addTrees = true;
            environmentSetup.treeCount = 25;
        }
        
        createPath = false;
    }
    
    void ConfigureUrban()
    {
        if (worldBuilder != null)
        {
            worldBuilder.obstacleCount = 15;
            worldBuilder.buildingCount = 12;
            worldBuilder.buildingMaxHeight = 12f;
        }
        
        if (environmentSetup != null)
        {
            environmentSetup.addTrees = false;
        }
        
        if (pathCreator != null)
        {
            pathCreator.pathRadius = 20f;
            pathCreator.pathWidth = 3f;
        }
    }
    
    void AddInteractiveElements()
    {
        // Add some interactive elements for testing
        CreateTargetMarkers();
        CreateSpawnPoints();
    }
    
    void CreateTargetMarkers()
    {
        for (int i = 0; i < 4; i++)
        {
            float angle = i * Mathf.PI * 0.5f;
            Vector3 position = new Vector3(
                Mathf.Cos(angle) * 30f,
                1f,
                Mathf.Sin(angle) * 30f
            );
            
            GameObject target = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            target.transform.position = position;
            target.transform.localScale = new Vector3(2f, 0.1f, 2f);
            
            Renderer renderer = target.GetComponent<Renderer>();
            renderer.material.color = Color.red;
            
            target.tag = "Target";
            target.name = $"Target_{i}";
        }
    }
    
    void CreateSpawnPoints()
    {
        // Create multiple spawn points for the robot
        Vector3[] spawnPositions = {
            Vector3.zero,
            new Vector3(5, 0, 5),
            new Vector3(-5, 0, 5),
            new Vector3(0, 0, -10)
        };
        
        foreach (Vector3 pos in spawnPositions)
        {
            GameObject spawnPoint = new GameObject("SpawnPoint");
            spawnPoint.transform.position = pos + Vector3.up * 0.5f;
            spawnPoint.tag = "SpawnPoint";
            
            // Add visual indicator
            GameObject indicator = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            indicator.transform.SetParent(spawnPoint.transform);
            indicator.transform.localPosition = Vector3.zero;
            indicator.transform.localScale = Vector3.one * 0.5f;
            
            Renderer renderer = indicator.GetComponent<Renderer>();
            renderer.material.color = Color.blue;
            renderer.material.SetFloat("_Mode", 2); // Fade mode
            Color color = renderer.material.color;
            color.a = 0.5f;
            renderer.material.color = color;
        }
    }
    
    [ContextMenu("Recreate World")]
    public void RecreateWorld()
    {
        // Clear existing world
        ClearWorld();
        
        // Recreate
        CreateTestWorld();
    }
    
    void ClearWorld()
    {
        // Clear all generated objects
        string[] tagsToClean = { "Obstacle", "Building", "Path", "Waypoint", "Target", "SpawnPoint", "Tree", "Ground" };
        
        foreach (string tag in tagsToClean)
        {
            GameObject[] objects = GameObject.FindGameObjectsWithTag(tag);
            for (int i = 0; i < objects.Length; i++)
            {
                DestroyImmediate(objects[i]);
            }
        }
    }
}