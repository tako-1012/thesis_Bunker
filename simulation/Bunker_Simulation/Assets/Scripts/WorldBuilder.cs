using UnityEngine;

public class WorldBuilder : MonoBehaviour
{
    [Header("World Generation Settings")]
    public int obstacleCount = 10;
    public Vector2 worldSize = new Vector2(50, 50);
    public GameObject obstaclePrefab;
    
    [Header("Building Settings")]
    public int buildingCount = 5;
    public float buildingMinHeight = 2f;
    public float buildingMaxHeight = 8f;
    
    void Start()
    {
        BuildWorld();
    }
    
    void BuildWorld()
    {
        // Clear existing obstacles
        ClearObstacles();
        
        // Create obstacles
        CreateObstacles();
        
        // Create simple buildings
        CreateBuildings();
        
        Debug.Log("World building completed!");
    }
    
    void ClearObstacles()
    {
        GameObject[] obstacles = GameObject.FindGameObjectsWithTag("Obstacle");
        for (int i = 0; i < obstacles.Length; i++)
        {
            DestroyImmediate(obstacles[i]);
        }
    }
    
    void CreateObstacles()
    {
        for (int i = 0; i < obstacleCount; i++)
        {
            // Random position within world bounds
            Vector3 position = new Vector3(
                Random.Range(-worldSize.x / 2, worldSize.x / 2),
                0,
                Random.Range(-worldSize.y / 2, worldSize.y / 2)
            );
            
            // Create cube obstacle
            GameObject obstacle = GameObject.CreatePrimitive(PrimitiveType.Cube);
            obstacle.transform.position = position + Vector3.up * 0.5f; // Half cube height above ground
            obstacle.transform.localScale = new Vector3(
                Random.Range(1f, 3f),
                Random.Range(0.5f, 2f),
                Random.Range(1f, 3f)
            );
            
            // Set material color
            Renderer renderer = obstacle.GetComponent<Renderer>();
            renderer.material.color = new Color(
                Random.Range(0.5f, 1f),
                Random.Range(0.3f, 0.7f),
                Random.Range(0.2f, 0.6f)
            );
            
            obstacle.tag = "Obstacle";
            obstacle.name = "Obstacle_" + i;
        }
    }
    
    void CreateBuildings()
    {
        for (int i = 0; i < buildingCount; i++)
        {
            // Random position for buildings (further from center)
            Vector3 position = new Vector3(
                Random.Range(-worldSize.x / 2, worldSize.x / 2),
                0,
                Random.Range(-worldSize.y / 2, worldSize.y / 2)
            );
            
            // Make sure buildings are not too close to center (0,0)
            if (Vector3.Distance(position, Vector3.zero) < 10f)
            {
                position = position.normalized * 15f;
            }
            
            // Create building
            GameObject building = GameObject.CreatePrimitive(PrimitiveType.Cube);
            float height = Random.Range(buildingMinHeight, buildingMaxHeight);
            building.transform.position = position + Vector3.up * height / 2;
            building.transform.localScale = new Vector3(
                Random.Range(3f, 8f),
                height,
                Random.Range(3f, 8f)
            );
            
            // Building material
            Renderer renderer = building.GetComponent<Renderer>();
            renderer.material.color = new Color(0.7f, 0.7f, 0.8f);
            
            building.tag = "Building";
            building.name = "Building_" + i;
        }
    }
    
    [ContextMenu("Rebuild World")]
    void RebuildWorld()
    {
        BuildWorld();
    }
}