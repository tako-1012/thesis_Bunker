using UnityEngine;

public class EnvironmentSetup : MonoBehaviour
{
    [Header("Lighting Settings")]
    public bool setupLighting = true;
    public Color skyboxColor = new Color(0.5f, 0.7f, 1f);
    public float lightIntensity = 1.2f;
    
    [Header("Ground Settings")]
    public bool createGround = true;
    public Vector2 groundSize = new Vector2(100, 100);
    public Material groundMaterial;
    
    [Header("Environment Objects")]
    public bool addTrees = true;
    public int treeCount = 15;
    public float treeAreaRadius = 40f;
    
    void Start()
    {
        SetupEnvironment();
    }
    
    void SetupEnvironment()
    {
        if (createGround)
        {
            CreateGround();
        }
        
        if (setupLighting)
        {
            SetupLighting();
        }
        
        if (addTrees)
        {
            CreateTrees();
        }
        
        SetupCamera();
        
        Debug.Log("Environment setup completed!");
    }
    
    void CreateGround()
    {
        // Check if ground already exists
        GameObject existingGround = GameObject.Find("Ground");
        if (existingGround != null)
        {
            DestroyImmediate(existingGround);
        }
        
        GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "Ground";
        ground.transform.position = Vector3.zero;
        ground.transform.localScale = new Vector3(groundSize.x / 10, 1, groundSize.y / 10);
        
        Renderer renderer = ground.GetComponent<Renderer>();
        if (groundMaterial != null)
        {
            renderer.material = groundMaterial;
        }
        else
        {
            // Create simple ground material
            renderer.material.color = new Color(0.3f, 0.6f, 0.3f); // Grass green
            renderer.material.mainTextureScale = new Vector2(groundSize.x / 5, groundSize.y / 5);
        }
        
        ground.tag = "Ground";
    }
    
    void SetupLighting()
    {
        // Setup main directional light (sun)
        Light[] lights = FindObjectsOfType<Light>();
        Light mainLight = null;
        
        foreach (Light light in lights)
        {
            if (light.type == LightType.Directional)
            {
                mainLight = light;
                break;
            }
        }
        
        if (mainLight == null)
        {
            GameObject lightGO = new GameObject("Directional Light");
            mainLight = lightGO.AddComponent<Light>();
            mainLight.type = LightType.Directional;
        }
        
        mainLight.intensity = lightIntensity;
        mainLight.color = Color.white;
        mainLight.transform.rotation = Quaternion.Euler(45f, -30f, 0f);
        
        // Setup ambient lighting
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = skyboxColor;
        RenderSettings.ambientEquatorColor = new Color(0.4f, 0.4f, 0.4f);
        RenderSettings.ambientGroundColor = new Color(0.2f, 0.2f, 0.2f);
        
        // Setup skybox
        RenderSettings.skybox = null; // Use solid color
        Camera.main.clearFlags = CameraClearFlags.SolidColor;
        Camera.main.backgroundColor = skyboxColor;
    }
    
    void CreateTrees()
    {
        for (int i = 0; i < treeCount; i++)
        {
            // Random position outside the main path area
            Vector3 position;
            do
            {
                position = new Vector3(
                    Random.Range(-treeAreaRadius, treeAreaRadius),
                    0,
                    Random.Range(-treeAreaRadius, treeAreaRadius)
                );
            } while (Vector3.Distance(position, Vector3.zero) < 25f); // Keep trees away from center path
            
            // Create simple tree (cylinder trunk + sphere leaves)
            GameObject tree = new GameObject($"Tree_{i}");
            tree.transform.position = position;
            
            // Trunk
            GameObject trunk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            trunk.transform.SetParent(tree.transform);
            trunk.transform.localPosition = Vector3.up * 1.5f;
            trunk.transform.localScale = new Vector3(0.3f, 1.5f, 0.3f);
            trunk.GetComponent<Renderer>().material.color = new Color(0.4f, 0.2f, 0.1f); // Brown
            
            // Leaves
            GameObject leaves = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            leaves.transform.SetParent(tree.transform);
            leaves.transform.localPosition = Vector3.up * 4f;
            leaves.transform.localScale = Vector3.one * Random.Range(2f, 3.5f);
            leaves.GetComponent<Renderer>().material.color = new Color(0.2f, 0.7f, 0.2f); // Green
            
            tree.tag = "Tree";
        }
    }
    
    void SetupCamera()
    {
        Camera mainCamera = Camera.main;
        if (mainCamera != null)
        {
            // Position camera for better overview
            mainCamera.transform.position = new Vector3(0, 15, -20);
            mainCamera.transform.rotation = Quaternion.Euler(25f, 0f, 0f);
            
            // Adjust camera settings for outdoor scene
            mainCamera.farClipPlane = 1000f;
            mainCamera.fieldOfView = 60f;
        }
    }
    
    [ContextMenu("Reset Environment")]
    void ResetEnvironment()
    {
        // Clear existing environment objects
        GameObject[] trees = GameObject.FindGameObjectsWithTag("Tree");
        GameObject[] ground = GameObject.FindGameObjectsWithTag("Ground");
        
        foreach (GameObject obj in trees)
        {
            DestroyImmediate(obj);
        }
        
        foreach (GameObject obj in ground)
        {
            DestroyImmediate(obj);
        }
        
        SetupEnvironment();
    }
}